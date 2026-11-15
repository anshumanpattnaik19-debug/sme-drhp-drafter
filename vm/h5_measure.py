"""H5 measurement: are the figures in the drafts grounded in the bundle files?

Inputs, per bundle, pulled from the VM run (vm/h5_run.py):
  build/h5/<bundle>/drafts.json   the drafted sections (blocks with text and tables)
  build/h5/<bundle>/blocks/*.json the text of every processed file, including OCR text

A figure, date, identifier, page reference or honorific name in a draft is grounded when the bundle's own text
contains it (the same check as the verifier, with the bundle text as the reference set instead of the fact store
only). Ungrounded values are the ones the verifier should mask.

    python vm/h5_measure.py build/h5
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verify.checks import Known, scan  # noqa: E402


def block_text(b):
    if b.get("type") == "table":
        return "\n".join(" | ".join(str(c) for c in r) for r in b.get("rows", []))
    return b.get("text", "") or ""


def bundle_pool(root: Path) -> list[dict]:
    pool = []
    for f in sorted((root / "blocks").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for b in d.get("blocks", d if isinstance(d, list) else []):
            t = b.get("text", "") if isinstance(b, dict) else ""
            if t:
                pool.append({"value": re.sub(r"\s+", " ", t)})
    return pool


def main(h5: Path):
    rows = []
    for bdir in sorted(p for p in h5.iterdir() if p.is_dir()):
        pool = bundle_pool(bdir)
        known = Known(pool, offer=None, context="")
        drafts = json.loads((bdir / "drafts.json").read_text(encoding="utf-8"))
        items = drafts.items() if isinstance(drafts, dict) else [(d.get("key"), d) for d in drafts]
        tot = {"figure": 0, "date": 0, "identifier": 0, "name": 0, "page_ref": 0, "small": 0}
        ungrounded = []
        sections = 0
        for key, sec in items:
            if not sec or sec.get("status") not in (None, "drafted") and not sec.get("blocks"):
                continue
            text = re.sub(r"\s+", " ", "\n".join(block_text(b) for b in sec.get("blocks", [])))
            if not text.strip():
                continue
            sections += 1
            for h in scan(text, known):
                kind = h["kind"]
                if kind in tot:
                    tot[kind] += 1
                if not h["grounded"]:
                    ungrounded.append((key, kind, h["raw"], text[max(0, h["start"] - 60):h["end"] + 20].replace("\n", " ")))
        total = sum(tot.values())
        bad = len(ungrounded)
        rows.append({"bundle": bdir.name, "sections_with_text": sections, "checked_values": total,
                     "ungrounded": bad, "grounded_share": round(1 - bad / total, 4) if total else None,
                     "ungrounded_examples": ungrounded[:12]})
        print(json.dumps({k: v for k, v in rows[-1].items() if k != "ungrounded_examples"}, ensure_ascii=False), flush=True)
        for u in ungrounded[:12]:
            print("   ", u[0], u[1], repr(u[2]), "|", u[3][:140], flush=True)
    (h5 / "h5_measure.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "build/h5"))
