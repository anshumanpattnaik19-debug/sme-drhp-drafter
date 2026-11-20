"""Where do a model's invented figures come from? Traces every figure in a draft that the inputs do not contain.

    python -m evaluate.invented_trace [predictions.jsonl] [--rows test.jsonl]

For each draft in a predictions file (default: the shipped model's, drive/runs/A_qa/predictions_A_qa_dpo.jsonl) it lists the
figures that are not in the prompt's inputs and sorts them by the most likely source, first match wins:

    copied      the figure is in the PRECEDENT block of the prompt (an example from another company)
    filed       the figure is in the filed text but not in the inputs
    reformatted the same number as an input, written differently
    small       a whole number under 100 (an address part, an age, a count)
    calculated  a sum, difference, ratio or percent of two input numbers
    unsourced   none of the above

"calculated" is checked against a control: the same test against the inputs of a random other draft. Matching by chance is
common, so only the excess over the control counts as real (19 Nov 2026: 12 of 33 against about 3 by chance). A match in the
training text is NOT reported as a source: it holds as often for correct figures as for invented ones (42% against 45%).

Also reported: the invention rate by section and by number of facts given. Written first as a one-off analysis on 19 Nov 2026.
"""
from __future__ import annotations

import collections
import itertools
import os
import random
import re
import sys

from evaluate import metrics as M


def num(s):
    try:
        return float(str(s).replace(",", "").replace("₹", "").replace("%", "").strip())
    except ValueError:
        return None


def derived(v, nums):
    """v equals a sum, difference, ratio or percent of two of the numbers (within rounding)."""
    if v is None:
        return False
    for a, b in itertools.combinations(nums[:60], 2):
        for c in (a + b, abs(a - b), a * b / 100 if b else None, a / b * 100 if b else None, b / a * 100 if a else None):
            if c is not None and abs(c - v) <= max(0.011, abs(v) * 0.002):
                return True
    return False


def src_numbers(row):
    return [n for n in (num(x) for x in M.figures(M.source_text(row))) if n is not None]


def classify(figure, row, rec_inputs, precedent_figs, gold_figs):
    v = num(figure)
    if figure in precedent_figs:
        return "copied"
    if figure in gold_figs:
        return "filed"
    if v is not None and any(abs(v - n) < 1e-6 for n in rec_inputs):
        return "reformatted"
    if v is not None and abs(v) < 100 and v == int(v):
        return "small"
    if derived(v, rec_inputs):
        return "calculated"
    return "unsourced"


def trace(rows, preds, seed=7):
    rng = random.Random(seed)
    inputs = {pid: src_numbers(r) for pid, r in rows.items() if "FACTS" in r["messages"][1]["content"]}
    ids = list(inputs)
    cats, per_section, per_facts, items = collections.Counter(), collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0]), []
    drafts = with_invented = 0
    for p in preds:
        row = rows.get(p["id"])
        if not row or p["id"] not in inputs:
            continue
        rec = M.draft_record(row, p)
        drafts += 1
        user = row["messages"][1]["content"]
        m = M.RE_PRECEDENT.search(user)
        prec = M.figures(m.group(0)) if m else set()
        gold = M.figures(row["messages"][-1]["content"])
        inv = rec["invented_figures"]
        with_invented += bool(inv)
        sec = (re.search(r"-([a-z_]+)-\d+-dra", p["id"]) or [None, "?"])[1]
        nf = len(M.facts_of(user))
        bucket = "0-5 facts" if nf <= 5 else "6-15 facts" if nf <= 15 else "16+ facts"
        for d, k in ((per_section, sec), (per_facts, bucket)):
            d[k][0] += bool(inv)
            d[k][1] += 1
        for f in inv:
            c = classify(f, row, inputs[p["id"]], prec, gold)
            cats[c] += 1
            items.append((p["id"], f, c))
    # control for "calculated": the same test against another draft's inputs
    cand = [(pid, num(f)) for pid, f, c in items if c in ("calculated", "unsourced")]
    chance = [sum(derived(v, inputs[rng.choice([i for i in ids if i != pid])]) for pid, v in cand) for _ in range(20)]
    return {"drafts": drafts, "with_invented": with_invented, "figures": sum(cats.values()), "classes": dict(cats),
            "by_section": {k: tuple(v) for k, v in per_section.items()}, "by_facts": {k: tuple(v) for k, v in per_facts.items()},
            "calculated_control": {"candidates": len(cand), "own_inputs": cats.get("calculated", 0),
                                   "random_inputs_mean": round(sum(chance) / len(chance), 1)}, "items": items}


def main(argv):
    rows_name = "test.jsonl"
    args = [a for a in argv if not a.startswith("--")]
    if "--rows" in argv:
        rows_name = argv[argv.index("--rows") + 1]
        args = [a for a in args if a != rows_name]
    path = args[0] if args else os.path.join(M.ROOT, "drive", "runs", "A_qa", "predictions_A_qa_dpo.jsonl")
    out = trace(M.load_rows(rows_name), M.load_preds(path))
    print(f"{path}\n{out['figures']} invented figures in {out['with_invented']} of {out['drafts']} drafts")
    for c, n in sorted(out["classes"].items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {100 * n / max(1, out['figures']):5.1f}%  {c}")
    cc = out["calculated_control"]
    print(f"calculated: {cc['own_inputs']} against about {cc['random_inputs_mean']} by chance (random other inputs, "
          f"{cc['candidates']} candidates)")
    for title, d in (("by section", out["by_section"]), ("by facts given", out["by_facts"])):
        print(title)
        for k, (a, n) in sorted(d.items(), key=lambda x: -x[1][1]):
            print(f"  {k:14s} {a:3d} of {n:3d} = {100 * a / n:4.0f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
