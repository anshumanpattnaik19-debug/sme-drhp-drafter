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


NUM = r"(?:-|[\d,]+(?:\.\d+)?)"
RE_THREE = re.compile(rf"^(?P<label>.*?[A-Za-z\)].*?)\s+(?P<a>{NUM})\s+(?P<b>{NUM})\s+(?P<c>{NUM})\s*$")


def _num(s):
    return 0.0 if s == "-" else float(s.replace(",", ""))


def reconcile(sec):
    """Deployment rows in the objects section: a label, the amount for year 1, the amount for year 2 and the total.
    The two years must add up to the total ('-' is zero). A row that does not add up is reported with its figures."""
    findings = []
    for b in sec.get("blocks", []):
        if b.get("type") == "table":
            # only tables rebuilt from the model's plain-text rows (draft/writer.py, "converted") have the
            # label, year, year, total order; the builder's own tables have their own column order and are not checked
            if not b.get("converted"):
                continue
            for r in b.get("rows", []):
                if len(r) == 4 and all(re.fullmatch(NUM, str(v).strip()) for v in r[1:]):
                    line = " ".join(str(v) for v in r)
                    m = RE_THREE.match(line)
                    if m:
                        a, bb, c = _num(m["a"]), _num(m["b"]), _num(m["c"])
                        if abs(a + bb - c) > 0.5:
                            findings.append(f"row does not add up: {m['label'][-50:]!r} {m['a']} + {m['b']} = {a + bb:,.2f}, total {m['c']}")
            continue
        for line in (b.get("text") or "").split("\n"):
            m = RE_THREE.match(line.strip())
            if not m:
                continue
            a, bb, c = _num(m["a"]), _num(m["b"]), _num(m["c"])
            if abs(a + bb - c) > 0.5:
                findings.append(f"row does not add up: {m['label'][-50:]!r} {m['a']} + {m['b']} = {a + bb:,.2f}, total {m['c']}")
    return findings


def qc_section(key, sec):
    findings = []
    if key == "objects":
        findings += reconcile(sec)
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
