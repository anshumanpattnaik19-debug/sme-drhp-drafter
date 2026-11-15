"""Make a digital PDF look like a scan: rasterise, grey, skew, noise, uneven light, JPEG, no text layer.

Deterministic: the noise is seeded from the file name, so the same input gives the same bytes.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageFilter


def _rng(name: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))


def degrade(img: Image.Image, seed_name: str) -> Image.Image:
    rng = _rng(seed_name)
    g = img.convert("L")
    angle = float(rng.uniform(-0.9, 0.9))
    g = g.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=245)
    a = np.asarray(g).astype(np.float32)
    h, w = a.shape
    # uneven light: a soft vignette and a darker band near one edge
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * rng.uniform(0.4, 0.6), h * rng.uniform(0.4, 0.6)
    r = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2)
    a = a * (1.0 - 0.12 * r) * (1.0 - 0.05 * (xx / w))
    a = a + rng.normal(0, 4.0, a.shape)          # sensor noise
    a = np.clip(a, 0, 255).astype(np.uint8)
    out = Image.fromarray(a).filter(ImageFilter.GaussianBlur(radius=0.45))
    # a faint punch-hole mark on the left edge
    d = np.asarray(out).copy()
    if rng.uniform() < 0.5:
        for yc in (int(h * 0.25), int(h * 0.75)):
            d[max(0, yc - 14):yc + 14, 10:34] = np.clip(d[max(0, yc - 14):yc + 14, 10:34] * 0.8, 0, 255)
    return Image.fromarray(d)


def _to_jpeg_bytes(img: Image.Image, quality: int = 55) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def scan_pdf(src: Path, dst: Path, dpi: int = 170) -> Path:
    src_doc = fitz.open(str(src))
    out = fitz.open()
    for i, page in enumerate(src_doc):
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = degrade(img, f"{src.name}:{i}")
        jpg = _to_jpeg_bytes(img)
        w_pt, h_pt = page.rect.width, page.rect.height
        np_ = out.new_page(width=w_pt, height=h_pt)
        np_.insert_image(np_.rect, stream=jpg)
    out.save(str(dst), garbage=3, deflate=True)
    out.close()
    src_doc.close()
    return dst


def scan_page_to_jpg(src_pdf: Path, dst: Path, dpi: int = 170) -> Path:
    doc = fitz.open(str(src_pdf))
    pix = doc[0].get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = degrade(img, f"{src_pdf.name}:img")
    dst.write_bytes(_to_jpeg_bytes(img, quality=58))
    doc.close()
    return dst


def image_to_scan_jpg(src_png: Path, dst: Path) -> Path:
    img = degrade(Image.open(src_png).convert("RGB"), src_png.name)
    dst.write_bytes(_to_jpeg_bytes(img, quality=60))
    return dst
