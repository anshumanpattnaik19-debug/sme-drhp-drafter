"""Score drafts made from the app-format prompts (trainset/out/test_app.jsonl) with the guard the app applies.

    python -m evaluate.score_app drive/runs/live/qa3/predictions_A_qa3_dpo.jsonl drive/runs/live/qa3/predictions_A_qa_dpo.jsonl ...

The prompts of test_app already hold the unknown and computed facts and no precedent, so each row is scored as it was given.
For each file: drafts with an invented figure in the raw text and after the guard, values masked per draft, fact use, loops, length.
"""
from __future__ import annotations

import json
import os
import re
import sys

from data.prompts import trim_repeats
from draft.writer import choose_draft, guard_draft
from evaluate import metrics as M
from evaluate.live_eval import guard_flat, prompt_parts

APP = os.path.join(M.ROOT, "trainset", "out", "test_app.jsonl")


def load_app():
    return {r["id"]: r for r in (json.loads(l) for l in open(APP, encoding="utf-8") if l.strip())}


def pick(row, candidates):
    """The draft the app would show: fewest loops, then fewest masked values, then most facts used (draft/writer.compose)."""
    _, _, facts, *_ = prompt_parts(row)
    scored = []
    for t in candidates:
        g, n, looped, _ = guard_flat(t, row)
        low = g.lower()
        used = sum(str(f["value"]).lower() in low for f in facts if len(str(f["value"])) >= 3 and str(f["value"]) != "[●]")
        scored.append(((looped, n, -used), len(g)))
    return candidates[choose_draft(scored)]


def score(path, rows=None):
    rows = rows or load_app()
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    for r in recs:                                                   # a best-of-n file: keep the draft the app would show
        if "candidates" in r and "prediction" not in r and r["id"] in rows:
            r["prediction"] = pick(rows[r["id"]], r["candidates"])
    recs = [r for r in recs if r.get("prediction") is not None and r["id"] in rows]
    a = {"n": 0, "raw_inv": 0, "ver_inv": 0, "masked": 0, "loops": 0, "own_raw": 0, "own_ver": 0, "own_tot": 0, "len": 0.0,
         }
    kinds, ids_inv = {}, []
    for r in recs:
        row = rows[r["id"]]
        raw = M.draft_record(row, {"id": r["id"], "prediction": r["prediction"], "raw": r["prediction"]})
        g, n, looped, _ = guard_flat(r["prediction"], row)
        ver = M.draft_record(row, {"id": r["id"], "prediction": g, "raw": g})
        a["n"] += 1
        a["raw_inv"] += bool(raw["invented_figures"])
        a["ver_inv"] += bool(ver["invented_figures"])
        if ver["invented_figures"]:
            ids_inv.append((r["id"], ver["invented_figures"][:3]))
        a["masked"] += n
        a["loops"] += bool(looped or trim_repeats(r["prediction"])[1])
        a["own_raw"] += raw["own_used"]
        a["own_ver"] += ver["own_used"]
        a["own_tot"] += raw["own_total"]
        a["len"] += len(g) / max(1, len(row["messages"][-1]["content"]))
        _, user, facts, company, section, sub = prompt_parts(row)
        blocks = guard_draft(r["prediction"], sub, facts, {}, company, re.sub(r"[^a-z0-9]", "", user.lower()))[0]
        for b in blocks:
            for h in b.get("masked", []):
                kinds[h["kind"]] = kinds.get(h["kind"], 0) + 1
    n = max(1, a["n"])
    print(f"\n{path}  ({a['n']} drafts)")
    print(f"  invented figure in raw text / after the guard : {a['raw_inv']:3d} = {100 * a['raw_inv'] / n:4.1f}%  /  {a['ver_inv']:3d} = {100 * a['ver_inv'] / n:4.1f}%")
    print(f"  values masked per draft                        : {a['masked'] / n:4.2f}   {dict(sorted(kinds.items(), key=lambda x: -x[1]))}")
    print(f"  fact use raw / after the guard                 : {a['own_raw'] / max(1, a['own_tot']):.3f} / {a['own_ver'] / max(1, a['own_tot']):.3f}")
    print(f"  drafts with a loop                             : {100 * a['loops'] / n:4.1f}%")
    print(f"  length against the filed text                  : {a['len'] / n:.2f}")
    if ids_inv:
        print("  still flagged after the guard:", ids_inv)
    return a


if __name__ == "__main__":
    rows = load_app()
    for p in sys.argv[1:]:
        score(p, rows)
