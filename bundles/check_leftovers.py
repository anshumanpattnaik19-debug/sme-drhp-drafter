"""Search a built bundle for source identity names that should have been retargeted.

    python check_leftovers.py <bundle_dir> <term> [<term> ...]

Reads text from PDF, DOCX and XLSX files (scanned JPEG pages have no text layer and are not searched).
"""
import sys
from pathlib import Path

import docx
import fitz
import openpyxl


def text_of(path: Path) -> str:
    if path.suffix == ".pdf":
        with fitz.open(str(path)) as d:
            return "\n".join(p.get_text() for p in d)
    if path.suffix == ".docx":
        doc = docx.Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for r in t.rows:
                parts += [c.text for c in r.cells]
        return "\n".join(parts)
    if path.suffix == ".xlsx":
        wb = openpyxl.load_workbook(str(path), data_only=True)
        return "\n".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
    return ""


if __name__ == "__main__":
    root = Path(sys.argv[1])
    terms = sys.argv[2:]
    total = 0
    for f in sorted(root.iterdir()):
        if f.name.startswith("_"):
            continue
        t = text_of(f)
        for term in terms:
            n = t.count(term)
            if n:
                total += n
                print(f"{f.name}: {term!r} x{n}")
    print("TOTAL LEFTOVERS", total)
