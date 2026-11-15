"""Readers for the five issuer input formats. Every block keeps file, page (or sheet/row) and kind.

    read_file(path) -> {"format", "pages", "blocks": [{"page", "loc", "kind", "text"}], "ocr_pages", "warnings"}

Digital PDF: PyMuPDF text per page. Scanned PDF pages (no text layer) and images go through OCR when
rapidocr-onnxruntime is installed (CPU); otherwise the page is kept with kind "needs_ocr" so the UI can
say so. Word: paragraphs and tables in document order. Excel: one block per non-empty row, cached values
(data_only) so formulas show their results. The production pipeline swaps in docling / PaddleOCR /
Qwen2.5-VL (PLAN.md section 4); the block shape stays the same.
"""
from __future__ import annotations

import os
import re

FORMATS = {
    ".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx", ".xlsm": "xlsx",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".tif": "image", ".tiff": "image", ".bmp": "image",
    ".txt": "text", ".md": "text", ".csv": "text",
}
MIN_TEXT_CHARS = 40          # a PDF page with less text than this is treated as scanned

_ocr_engine = None
_ocr_checked = False
_ocr_error = None


def ocr_engine():
    """Lazy RapidOCR instance, or None when the package is not installed."""
    global _ocr_engine, _ocr_checked
    if not _ocr_checked:
        _ocr_checked = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception as e:  # noqa: BLE001 - optional dependency; the reason is shown in /api/health
            _ocr_engine = None
            global _ocr_error
            _ocr_error = f"{type(e).__name__}: {e}"
    return _ocr_engine


OCR_PROMPT = (
    "Transcribe all the text on this page exactly as printed, in reading order. Keep each table row on its own line "
    "and separate cells with ' | '. Keep numbers, dates, names and punctuation exactly. Output only the transcription, "
    "with no commentary."
)

# Vision LLM used for OCR: {"url": ".../v1", "model": "...", "api_key": ""} or None (RapidOCR only).
_llm_ocr = None
last_ocr_error = None


def set_llm_ocr(cfg):
    """Set (or clear, with None) the vision model used for OCR. Called by the app before each processing run."""
    global _llm_ocr
    _llm_ocr = cfg if cfg and cfg.get("url") and cfg.get("model") else None


def _ocr_llm(data: bytes) -> str:
    import base64

    import httpx

    url = _llm_ocr["url"].rstrip("/")
    headers = {"Authorization": f"Bearer {_llm_ocr['api_key']}"} if _llm_ocr.get("api_key") else {}
    body = {
        "model": _llm_ocr["model"], "temperature": 0.0, "max_tokens": 3000,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(data).decode()}},
        ]}],
    }
    r = httpx.post(f"{url}/chat/completions", json=body, headers=headers, timeout=300)
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def ocr_available() -> bool:
    return _llm_ocr is not None or ocr_engine() is not None


def file_format(path: str) -> str | None:
    return FORMATS.get(os.path.splitext(path)[1].lower())


def _ocr_image_bytes(data: bytes) -> str | None:
    """Text of one page image: the vision LLM when configured, otherwise the offline RapidOCR engine.

    If the LLM endpoint fails for a page, that page falls back to RapidOCR and the error is kept in last_ocr_error.
    """
    global last_ocr_error
    if _llm_ocr is not None:
        try:
            text = _ocr_llm(data)
            last_ocr_error = None
            return text
        except Exception as e:  # noqa: BLE001 - endpoint problems must not stop the file
            last_ocr_error = f"LLM OCR failed, used RapidOCR: {e}"
    eng = ocr_engine()
    if eng is None:
        return None
    result, _ = eng(data)
    if not result:
        return ""
    # result: [[box, text, score], ...]; rebuild lines by vertical position
    rows = sorted(((b[0][1], b[0][0], t) for b, t, _s in result), key=lambda r: (round(r[0] / 12), r[1]))
    lines, cur, last_y = [], [], None
    for y, _x, t in rows:
        if last_y is not None and abs(y - last_y) > 12:
            lines.append(" ".join(cur))
            cur = []
        cur.append(t)
        last_y = y
    if cur:
        lines.append(" ".join(cur))
    return _space_dates("\n".join(lines))


RE_COMPACT_DATE = re.compile(
    r"\b(\d{1,2})(st|nd|rd|th)?\s*(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s*((?:19|20)\d{2})\b", re.I)


def _space_dates(text: str) -> str:
    """OCR often drops the spaces in a date ("21September2023"). Put them back, so the date and its label read as text."""
    return RE_COMPACT_DATE.sub(lambda m: f"{m.group(1)}{m.group(2) or ''} {m.group(3)} {m.group(4)}", text)


PAGE_NUMBER_RE = re.compile(r"^(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?$", re.I)


def _line_key(line):
    """A running line is compared as written (spacing and case aside). Digits are kept, so a body sentence that
    differs only by its numbers is not taken for a header."""
    return re.sub(r"\s+", " ", line).strip().lower()


def strip_running_lines(blocks, min_pages=3):
    """Remove running headers, footers and page numbers from the text pages of one file, in place.

    A short line (up to 160 characters) that repeats exactly on at least `min_pages` pages and on at least 40% of
    the text pages is a running header or footer. A line that is only a page number ("12", "Page 12", "Page 12 of 80") is removed on every page. Without
    this, a footer is read as body text and gets copied into the drafts ("... Restated Financial Information Page 2
    qualifications ...").
    """
    text_blocks = [b for b in blocks if b.get("kind") == "text"]
    seen = {}
    for b in text_blocks:
        for k in {_line_key(x) for x in b["text"].splitlines() if x.strip() and len(x.strip()) <= 160}:
            if k:
                seen[k] = seen.get(k, 0) + 1
    repeated = {k for k, n in seen.items() if n >= min_pages and n >= 0.4 * len(text_blocks)}
    for b in text_blocks:
        kept = []
        for line in b["text"].splitlines():
            t = line.strip()
            if t and (PAGE_NUMBER_RE.match(t) or (len(t) <= 160 and _line_key(t) in repeated)):
                continue
            kept.append(line)
        b["text"] = "\n".join(kept).strip()
    return blocks


def _read_pdf(path, ocr, ocr_limit=None, progress=None):
    import fitz
    blocks, ocr_pages, warnings = [], [], []
    with fitz.open(path) as doc:
        n = doc.page_count
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) >= MIN_TEXT_CHARS:
                blocks.append({"page": i, "loc": f"p. {i}", "kind": "text", "text": text})
                continue
            if ocr and (ocr_limit is None or len(ocr_pages) < ocr_limit):
                if progress:
                    progress(f"OCR page {i} of {n}")
                pix = page.get_pixmap(dpi=200)
                got = _ocr_image_bytes(pix.tobytes("png"))
                if got is not None:
                    ocr_pages.append(i)
                    blocks.append({"page": i, "loc": f"p. {i}", "kind": "ocr", "text": got})
                    continue
            blocks.append({"page": i, "loc": f"p. {i}", "kind": "needs_ocr", "text": text})
    strip_running_lines(blocks)
    skipped = sum(b["kind"] == "needs_ocr" for b in blocks)
    if skipped and ocr and ocr_available():
        warnings.append(f"{skipped} scanned page(s) skipped: OCR page limit reached (raise it in Settings).")
    elif skipped and ocr:
        warnings.append("Scanned pages found but OCR is not installed (pip install rapidocr-onnxruntime).")
    elif skipped:
        warnings.append(f"{skipped} scanned page(s) not read: OCR is switched off in Settings.")
    return n, blocks, ocr_pages, warnings


def _read_docx(path):
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(path)
    blocks, para_no, table_no = [], 0, 0
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, d).text.strip()
            if text:
                para_no += 1
                blocks.append({"page": None, "loc": f"para {para_no}", "kind": "text", "text": text})
        elif tag == "tbl":
            table_no += 1
            rows = []
            for r in Table(child, d).rows:
                cells, seen = [], set()
                for c in r.cells:            # merged cells repeat; keep each once
                    if id(c._tc) in seen:
                        continue
                    seen.add(id(c._tc))
                    # a line break inside a cell ("Name\nDesignation") must not start a new table row
                    cells.append("; ".join(p.strip() for p in c.text.split("\n") if p.strip()).replace(" | ", " / "))
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append({"page": None, "loc": f"table {table_no}", "kind": "table", "text": "\n".join(rows)})
    return None, blocks, [], []


def _fmt_cell(v, number_format=""):
    if v is None:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and "%" in (number_format or ""):
        return f"{v * 100:.2f}%"         # Excel keeps 56% as 0.56; show what the issuer sees
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) < 1e15 else str(v)
    if hasattr(v, "strftime"):
        return v.strftime("%d %B %Y")
    return str(v).strip()


def _read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    blocks = []
    for ws in wb.worksheets:
        for r_idx, row in enumerate(ws.iter_rows(), start=1):
            cells = [_fmt_cell(getattr(c, "value", None), getattr(c, "number_format", "")) for c in row]
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                blocks.append({"page": None, "loc": f"{ws.title}!{r_idx}", "kind": "row", "text": " | ".join(cells),
                               "sheet": ws.title, "row": r_idx})
    wb.close()
    return None, blocks, [], []


def _read_image(path, ocr):
    with open(path, "rb") as fh:
        data = fh.read()
    got = _ocr_image_bytes(data) if ocr else None
    if got is None:
        why = "OCR is switched off in Settings." if not ocr else "OCR is not installed (pip install rapidocr-onnxruntime)."
        return 1, [{"page": 1, "loc": "image", "kind": "needs_ocr", "text": ""}], [], [f"Image not read: {why}"]
    return 1, [{"page": 1, "loc": "image", "kind": "ocr", "text": got}], [1], []


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = [ln.rstrip() for ln in fh]
    return None, [{"page": None, "loc": f"line {i}", "kind": "text", "text": ln}
                  for i, ln in enumerate(lines, start=1) if ln.strip()], [], []


def read_file(path: str, ocr: bool = True, ocr_limit: int | None = None, progress=None) -> dict:
    fmt = file_format(path)
    if fmt is None:
        raise ValueError(f"unsupported file type: {os.path.basename(path)}")
    if fmt == "pdf":
        pages, blocks, ocr_pages, warnings = _read_pdf(path, ocr, ocr_limit, progress)
    elif fmt == "docx":
        pages, blocks, ocr_pages, warnings = _read_docx(path)
    elif fmt == "xlsx":
        pages, blocks, ocr_pages, warnings = _read_xlsx(path)
    elif fmt == "image":
        if progress and ocr:
            progress("OCR image")
        pages, blocks, ocr_pages, warnings = _read_image(path, ocr)
    else:
        pages, blocks, ocr_pages, warnings = _read_text(path)
    if fmt == "pdf" and ocr_pages:
        fmt = "pdf_scanned" if len(ocr_pages) == pages else "pdf_mixed"
    elif fmt == "pdf" and any(b["kind"] == "needs_ocr" for b in blocks):
        fmt = "pdf_scanned" if all(b["kind"] == "needs_ocr" for b in blocks) else "pdf_mixed"
    return {"format": fmt, "pages": pages, "blocks": blocks, "ocr_pages": ocr_pages, "warnings": warnings,
            "chars": sum(len(b["text"]) for b in blocks)}
