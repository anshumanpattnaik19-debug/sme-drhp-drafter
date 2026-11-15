"""Transcribe the OCR test set with a vision model served by vLLM (run on the VM, see vm/ocr_eval.sbatch).

Uses the same prompt as the app's LLM OCR route (ingest/readers.py, OCR_PROMPT), temperature 0.

    python vm/ocr_eval_vllm.py ~/sme/ocr_eval http://127.0.0.1:8012/v1 qwen-vl ~/sme/ocr_eval/transcripts_qwen_vl.json
"""
import base64
import json
import sys
from pathlib import Path

import httpx

OCR_PROMPT = (
    "Transcribe all the text on this page exactly as printed, in reading order. Keep each table row on its own line "
    "and separate cells with ' | '. Keep numbers, dates, names and punctuation exactly. Output only the transcription, "
    "with no commentary."
)


def transcribe(url, model, png: bytes) -> str:
    body = {"model": model, "temperature": 0.0, "max_tokens": 3000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
            ]}]}
    r = httpx.post(f"{url.rstrip('/')}/chat/completions", json=body, timeout=300)
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def main(eval_dir: Path, url: str, model: str, out: Path):
    manifest = json.loads((eval_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for m in manifest:
        png = (eval_dir / "images" / f"{m['id']}.png").read_bytes()
        rows.append({"id": m["id"], "text": transcribe(url, model, png)})
        print("transcribed", m["id"], flush=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]))
