"""QC of the drafted sections from an H5 run (build/h5_job<N>/<bundle>/drafts.json).

Checks per section: empty or near-empty text, paragraphs cut off mid-sentence, repeated sentences (loops), the
share of placeholders, and any leftover template or page-reference text. Writes a list of findings per bundle.

    python vm/h5_qc.py build/h5_job64
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

END_OK = re.compile(r"[.!?:;)”\"'\]|]\s*$|\[●\]\s*$")


def block_texts(sec):
    for b in sec.get("blocks", []):
        if b.get("type") == "table":
            for r in b.get("rows", []):
                yield "table", " | ".join(str(c) for c in r)
        else:
            yield b.get("type", "paragraph"), b.get("text", "") or ""


def qc_section(key, sec):
    findings = []
    paras = [t for k, t in block_texts(sec) if k in ("paragraph", "bullet", "list") and t.strip()]
    words = sum(len(t.split()) for k, t in block_texts(sec))
    if words < 15 and not sec.get("blocks"):
        findings.append("empty section")
    for t in paras:
        # a bullet or a table-like line is not a sentence; only prose can be cut off
        if not END_OK.search(t) and len(t) > 40 and "|" not in t and not t.lstrip().startswith("•"):
            findings.append(f"cut off: ...{t[-70:]!r}")
    sents = [s.strip() for t in paras for s in re.split(r"(?<=[.])\s+", t) if len(s.strip()) > 40]
    rep = [s for s, n in Counter(sents).items() if n > 1]
    if rep:
        findings.append(f"repeated sentence x{max(Counter(sents)[s] for s in rep)}: {rep[0][:80]!r}")
    alltext = " ".join(t for _, t in block_texts(sec))
    ph = alltext.count("[●]")
    if words and ph / max(1, words) > 0.15:
        findings.append(f"placeholders {ph} in {words} words")
    if re.search(r"\bPage \d+\b", alltext):
        findings.append("page reference in text")
    return {"words": words, "placeholders": ph, "findings": findings}


def main(root: Path):
    report = {}
    for bdir in sorted(p for p in root.iterdir() if p.is_dir()):
        d = json.loads((bdir / "drafts.json").read_text(encoding="utf-8"))
        items = d.items() if isinstance(d, dict) else [(x.get("key"), x) for x in d]
        rows = {}
        for k, sec in items:
            if sec and sec.get("blocks"):
                rows[k] = qc_section(k, sec)
        report[bdir.name] = rows
        bad = {k: r["findings"] for k, r in rows.items() if r["findings"]}
        print(f"== {bdir.name}: {len(rows)} sections, {len(bad)} with findings, "
              f"{sum(r['words'] for r in rows.values())} words", flush=True)
        for k, f in bad.items():
            for x in f:
                print(f"   {k}: {x}", flush=True)
    (root / "qc.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "build/h5_job64"))
