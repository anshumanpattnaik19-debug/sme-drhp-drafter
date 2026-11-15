"""The OCR route: a vision LLM on an OpenAI-compatible endpoint, with RapidOCR as the offline fallback.

A local stub server stands in for the vision model: it checks that the page image arrives as a base64 data URL and
answers with a fixed transcription. No network access is needed.
"""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import fitz
import pytest

from ingest import readers

TEXT = "CERTIFICATE OF INCORPORATION\nKestrel Flexipak Limited | CIN U22220GJ2014PLC083591"


class _Stub(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.seen.append(body)
        out = json.dumps({"choices": [{"message": {"content": TEXT}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # keep test output quiet
        pass


@pytest.fixture
def stub_url():
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Stub.seen = []
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()
    readers.set_llm_ocr(None)


def _scan_pdf(tmp_path: Path) -> Path:
    """A one-page PDF with no text layer: a picture of text, as a scan has."""
    src = fitz.open()
    page = src.new_page()
    page.insert_text((72, 72), "scanned text " * 20)
    pix = page.get_pixmap(dpi=100)
    out = fitz.open()
    p2 = out.new_page(width=page.rect.width, height=page.rect.height)
    p2.insert_image(p2.rect, pixmap=pix)
    path = tmp_path / "scan.pdf"
    out.save(str(path))
    return path


def test_llm_ocr_sends_the_page_image_and_uses_the_answer(stub_url, tmp_path):
    readers.set_llm_ocr({"url": stub_url, "model": "qwen2.5-vl-7b-instruct", "api_key": ""})
    res = readers.read_file(str(_scan_pdf(tmp_path)), ocr=True, ocr_limit=5)
    assert res["ocr_pages"] == [1]
    assert any(b["kind"] == "ocr" and b["text"] == TEXT for b in res["blocks"])
    req = _Stub.seen[-1]
    assert req["model"] == "qwen2.5-vl-7b-instruct"
    img = req["messages"][0]["content"][1]["image_url"]["url"]
    assert img.startswith("data:image/png;base64,")
    assert base64.b64decode(img.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"


def test_unreachable_llm_falls_back_to_rapidocr(tmp_path):
    readers.set_llm_ocr({"url": "http://127.0.0.1:9/v1", "model": "x", "api_key": ""})
    res = readers.read_file(str(_scan_pdf(tmp_path)), ocr=True, ocr_limit=5)
    assert readers.last_ocr_error and "LLM OCR failed" in readers.last_ocr_error
    # the file is still read (by RapidOCR when installed; otherwise the page stays "needs_ocr")
    assert res["pages"] == 1


def test_no_llm_configured_means_rapidocr_only(tmp_path):
    readers.set_llm_ocr(None)
    assert readers._llm_ocr is None
    res = readers.read_file(str(_scan_pdf(tmp_path)), ocr=True, ocr_limit=5)
    assert res["pages"] == 1
