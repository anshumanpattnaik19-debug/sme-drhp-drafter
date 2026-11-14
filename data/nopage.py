"""Derive the page-reference-free training files from the built ones (3 Nov 2026): the same rows, with page locators
cut out of drafting targets, section outlines, previous-sub-section summaries and precedents
(`clean.strip_page_refs`), so a run on them differs from run A only in the page references. FACTS and extraction rows are untouched.

    python -m data.nopage trainset/out      # writes train_nopage.jsonl and test_nopage.jsonl beside the originals
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .clean import strip_page_refs


def clean_row(r):
    if r["metadata"]["skill"] != "drafting":
        return r, 0
    sys_m, user, gold = r["messages"]
    head, rest = user["content"].split("FACTS: ", 1)
    facts, tail = (rest.split("\nPRECEDENT", 1) + [None])[:2]
    new_head, n_prev = strip_page_refs(head)            # outline headings and the previous-sub-section summary
    content = new_head + "FACTS: " + facts
    n_prec = 0
    if tail is not None:
        new_tail, n_prec = strip_page_refs(tail)
        content += "\nPRECEDENT" + new_tail
    target, n_gold = strip_page_refs(gold["content"])
    out = {**r, "messages": [sys_m, {**user, "content": content}, {**gold, "content": target}]}
    return out, (n_gold > 0) + 2 * (n_prev > 0) + 4 * (n_prec > 0)


def main(out_dir):
    out_dir = Path(out_dir)
    for split in ("train", "test"):
        rows = [json.loads(l) for l in open(out_dir / f"{split}.jsonl", encoding="utf-8")]
        res = [clean_row(r) for r in rows]
        with open(out_dir / f"{split}_nopage.jsonl", "w", encoding="utf-8") as fh:
            for r, _ in res:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        flags = [f for _, f in res]
        print(f"{split}_nopage.jsonl: {len(rows)} rows | changed targets {sum(f & 1 > 0 for f in flags)}, "
              f"outlines or previous summaries {sum(f & 2 > 0 for f in flags)}, precedents {sum(f & 4 > 0 for f in flags)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "trainset/out")
