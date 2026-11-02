"""Teacher screen (PLAN.md section 10, Week 0): two candidate teachers on the same 30 units, scored by the gates
and, on the 10 units the reviewer labelled, against the reviewer's facts.

    python -m teacher.screen select --n 30                      # -> trainset/screen/screen_units.jsonl + screen_jobs.jsonl
    python -m teacher.screen score --responses A.jsonl B.jsonl --labels trainset/screen/reviewer_labels.json

Pass rule (fixed in PLAN.md): precision >= 95% and coverage >= 85% (share of units whose drafting gates pass).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.facts import _num, apply_gates, normalise, parse_dates  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREEN = os.path.join(ROOT, "trainset", "screen")
PRECISION_MIN, COVERAGE_MIN = 0.95, 0.85


def _r(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def select(n=30, seed=7):
    """30 train units across the five core sections and two sizes, none from the sampled training rows' companies' test."""
    units = [u for u in _r(os.path.join(ROOT, "trainset", "work", "sampled_train.jsonl")) if u["skill"] == "drafting"]
    rnd = random.Random(seed)
    by = defaultdict(list)
    for u in units:
        by[u["outline_key"]].append(u)
    picked = []
    keys = sorted(by)
    while len(picked) < n and any(by.values()):
        for k in keys:
            if by[k] and len(picked) < n:
                picked.append(by[k].pop(rnd.randrange(len(by[k]))))
    os.makedirs(SCREEN, exist_ok=True)
    with open(os.path.join(SCREEN, "screen_units.jsonl"), "w", encoding="utf-8") as fh:
        for u in picked:
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")
    with open(os.path.join(SCREEN, "screen_jobs.jsonl"), "w", encoding="utf-8") as fh:
        for u in picked:
            fh.write(json.dumps({k: u[k] for k in ("unit_id", "section_title", "heading", "raw")}, ensure_ascii=False) + "\n")
    return picked


def _key(f):
    if f["type"] == "date" and parse_dates(f["value"]):
        return ("d", min(parse_dates(f["value"])))
    k = _num(re.sub(r"[^\d.,()-]", "", f["value"])) if re.search(r"\d", f["value"]) else None
    return ("n", k) if k is not None else ("t", " ".join(re.findall(r"[a-z0-9]+", f["value"].lower())))


def score(responses, units, labels=None):
    by_id = {u["unit_id"]: u for u in units}
    out = {"units": 0, "parsed": 0, "gate_pass": 0, "facts": 0, "precise": 0, "latency_s": [], "vs_reviewer": None}
    rev_tp = rev_n = t_n = 0
    for r in responses:
        u = by_id.get(r["unit_id"])
        if not u:
            continue
        out["units"] += 1
        out["latency_s"].append(r.get("latency_s") or 0)
        if r.get("facts") is None:
            continue
        out["parsed"] += 1
        facts, _ = normalise(r["facts"])
        _kept, g = apply_gates(facts, u["raw"], u["target"], u["masked_values"])
        out["gate_pass"] += g["pass"]
        out["facts"] += g["facts_in"]
        out["precise"] += g["facts_in"] - g["dropped"]["imprecise"]
        if labels and u["unit_id"] in labels:
            gold = {_key(f) for f in labels[u["unit_id"]]}
            got = {_key(f) for f in facts}
            rev_tp += len(gold & got)
            rev_n += len(gold)
            t_n += len(got)
    n = out["units"] or 1
    out["precision"] = round(out["precise"] / out["facts"], 3) if out["facts"] else 0
    out["coverage"] = round(out["gate_pass"] / n, 3)
    out["parse_rate"] = round(out["parsed"] / n, 3)
    out["latency_s"] = round(sum(out["latency_s"]) / n, 2)
    if rev_n:
        out["vs_reviewer"] = {"recall": round(rev_tp / rev_n, 3), "precision": round(rev_tp / t_n, 3) if t_n else 0}
    out["passes"] = out["precision"] >= PRECISION_MIN and out["coverage"] >= COVERAGE_MIN
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "score"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--responses", nargs="*")
    ap.add_argument("--labels")
    a = ap.parse_args()
    if a.cmd == "select":
        print(f"{len(select(a.n))} units -> {SCREEN}")
        return
    units = _r(os.path.join(SCREEN, "screen_units.jsonl"))
    labels = json.load(open(a.labels, encoding="utf-8")) if a.labels else None
    lines = ["| teacher | units | parsed | precision | coverage (gate pass) | vs reviewer recall / precision | s per call | passes |", "|---|---|---|---|---|---|---|---|"]
    for p in a.responses:
        rs = _r(p)
        s = score(rs, units, labels)
        vr = s["vs_reviewer"] or {}
        model = rs[0].get("model") if rs else p
        lines.append(f"| {model} | {s['units']} | {s['parse_rate']} | {s['precision']} | {s['coverage']} | "
                     f"{vr.get('recall', '–')} / {vr.get('precision', '–')} | {s['latency_s']} | {'yes' if s['passes'] else 'no'} |")
    report = "\n".join(lines)
    with open(os.path.join(SCREEN, "SCREEN_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Teacher screen\n\nPass rule: precision >= {PRECISION_MIN}, coverage >= {COVERAGE_MIN}.\n\n{report}\n")
    print(report)


if __name__ == "__main__":
    main()
