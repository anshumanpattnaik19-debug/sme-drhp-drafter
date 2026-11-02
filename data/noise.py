"""OCR-style noise for 30% of the extraction rows (PLAN.md 5.5), so the extractor also learns to read scans.

The errors imitate what the CPU OCR produced on the Ashtavira bundle: spaces dropped between words, confusable
characters, the rupee sign misread, stray line breaks. `render_ocr` (optional, slow) renders the text to an
image and reads it back with RapidOCR for a small real-OCR slice.
"""
from __future__ import annotations

import random

CONFUSE = {"0": "O", "O": "0", "1": "l", "l": "1", "5": "S", "S": "5", "rn": "m", "m": "rn", "₹": "Rs", ",": ".", "e": "c"}


def ocr_noise(text, seed=0, rate=0.03):
    rnd = random.Random(seed)
    words = text.split(" ")
    out = []
    for w in words:
        r = rnd.random()
        if out and r < rate * 4:
            out[-1] = out[-1] + w                      # dropped space
            continue
        if r < rate * 5 and len(w) > 2:
            for k, v in CONFUSE.items():
                if k in w and rnd.random() < 0.5:
                    w = w.replace(k, v, 1)
                    break
        if r > 1 - rate:
            w = w + "\n"
        out.append(w)
    return " ".join(out).replace("\n ", "\n")


def render_ocr(text, width=1240):
    """Real OCR round trip (needs Pillow and rapidocr-onnxruntime). Returns None when unavailable."""
    try:
        from PIL import Image, ImageDraw
        from ingest.readers import _ocr_image_bytes
        import io
        import textwrap
        lines = []
        for para in text.split("\n"):
            lines += textwrap.wrap(para, 110) or [""]
        img = Image.new("L", (width, 24 * len(lines) + 40), 255)
        d = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            d.text((20, 20 + 24 * i), ln, fill=0)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return _ocr_image_bytes(buf.getvalue())
    except Exception:  # noqa: BLE001 - optional
        return None
