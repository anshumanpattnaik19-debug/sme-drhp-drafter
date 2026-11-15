"""Build the OCR test set from the Kestrel bundle: scanned pages with their digital text as ground truth.

The scanned inputs are the bundle's own scanned files (scan_pdf and scan_jpg kinds). The digital original of each is
kept in the bundle's _work folder as <name>.pdf (or <name>.jpg.pdf), so the true text of every page is known.

    python vm/ocr_eval_make_set.py bundles/out/kestrel_flexipak build/ocr_eval

Writes build/ocr_eval/images/<id>.png (what the OCR engines see: a 200 dpi render of the scanned page), and
build/ocr_eval/truth/<id>.txt (the digital text of the same page), plus manifest.json.
"""
import json
import sys
from pathlib import Path

import fitz

PAGES_PER_PDF = 4
SCANNED_PDFS = ["04_Audited_FS_FY2024-25.pdf", "05_Audited_FS_FY2023-24.pdf"]
SCANNED_JPGS = ["01_Certificate_of_Incorporation_2012.jpg", "03_Factory_Licence.jpg", "04_GPCB_Consent_CCA.jpg"]


def main(bundle: Path, out: Path):
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in SCANNED_PDFS:
        scanned = fitz.open(str(bundle / name))
        raw = fitz.open(str(bundle / "_work" / name))
        for i in range(min(PAGES_PER_PDF, scanned.page_count)):
            pid = f"{Path(name).stem}_p{i + 1}"
            pix = scanned[i].get_pixmap(dpi=200)
            (out / "images" / f"{pid}.png").write_bytes(pix.tobytes("png"))
            (out / "truth" / f"{pid}.txt").write_text(raw[i].get_text("text"), encoding="utf-8")
            manifest.append({"id": pid, "source": name, "page": i + 1, "kind": "scanned_pdf_page"})
        scanned.close()
        raw.close()
    for name in SCANNED_JPGS:
        pid = Path(name).stem
        raw = fitz.open(str(bundle / "_work" / (name + ".pdf")))
        (out / "images" / f"{pid}.png").write_bytes(fitz.Pixmap(str(bundle / name)).tobytes("png"))
        (out / "truth" / f"{pid}.txt").write_text(raw[0].get_text("text"), encoding="utf-8")
        raw.close()
        manifest.append({"id": pid, "source": name, "page": 1, "kind": "scanned_jpg"})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{len(manifest)} pages written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
