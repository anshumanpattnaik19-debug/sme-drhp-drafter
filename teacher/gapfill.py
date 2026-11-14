"""Gap-fill: a second, targeted teacher pass for drafting units that failed the coverage gate.

    python -m teacher.gapfill jobs  --responses trainset/work/teacher_responses.jsonl --out trainset/work/gapfill_jobs.jsonl
    (Colab, A100: notebook stage 2b runs the jobs with teacher.driver -> MyDrive/sme_drhp/work/gapfill_responses.jsonl)
    python -m teacher.gapfill merge --responses trainset/work/teacher_responses.jsonl \
        --gapfill trainset/work/gapfill_responses.jsonl --out trainset/work/teacher_responses_merged.jsonl
    python -m data.build rows --responses trainset/work/teacher_responses_merged.jsonl

A unit is picked when it is a drafting unit, fails the gates because figures, dates or names of its target are not in
the facts, and could still become a row: everything missing is listed (at most 20 figures, 10 dates, 10 names) and
the kept facts plus the missing items fit MAX_OWN. The prompt lists the missed items as written in the passage. New
facts are appended to the first-pass facts; the gates still check every one of them when the rows are built.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.clean import strip_page_refs, strip_tables  # noqa: E402
from data.facts import RE_DATES, RE_FIG, _num, apply_gates, normalise, parse_dates  # noqa: E402
from data.pairs import MAX_OWN, MIN_DRAFT_WORDS  # noqa: E402
from teacher.prompts import gapfill_messages  # noqa: E402

LIMITS = {"figures": 20, "dates": 10, "names": 10}


def _surface_figures(target, values):
    """Each missing figure as the target writes it ("1,405.09", "(6.9)"), not as a float."""
    seen = {}
    for m in RE_FIG.finditer(target):
        k = _num(m.group(0).strip("()").rstrip(","))
        if k is not None:
            seen.setdefault(abs(k), m.group(0).strip().rstrip(","))
    return [seen.get(v, f"{v:g}") for v in values]


def _surface_dates(target, isodates):
    found = {}
    for rx in RE_DATES:
        for m in rx.finditer(target):
            for d in parse_dates(m.group(0)):
                found.setdefault(str(d), m.group(0))
    return [found.get(d, d) for d in isodates]


def select(units, responses):
    """Gap-fill jobs (with their prompts) for the drafting units that fail only on coverage and could become rows."""
    resp = {r["unit_id"]: r for r in responses}
    jobs, skipped = [], {"passed": 0, "no_response": 0, "nothing_missing": 0, "too_many_missing": 0, "table_only": 0}
    for u in units:
        if u.get("skill") != "drafting":
            continue
        r = resp.get(u["unit_id"])
        if not r or r.get("facts") is None:
            skipped["no_response"] += 1
            continue
        target, n_tables = strip_tables(u["target"])           # the same target the rows are built on
        target = strip_page_refs(target)[0]
        if n_tables and len(re.findall(r"[A-Za-z]{2,}", target)) < MIN_DRAFT_WORDS:
            skipped["table_only"] += 1
            continue
        facts, _ = normalise(r["facts"])
        kept, g = apply_gates(facts, u["raw"], target, u["masked_values"])
        if g["pass"]:
            skipped["passed"] += 1
            continue
        n = g["n_missing"]
        if not sum(n.values()):
            skipped["nothing_missing"] += 1                    # no facts and nothing to cover: generic prose
            continue
        if any(n[k] > LIMITS[k] for k in LIMITS) or len(kept) + sum(n.values()) > MAX_OWN:
            skipped["too_many_missing"] += 1
            continue
        missed = {"figures": _surface_figures(target, g["missing"]["figures"]),
                  "dates": _surface_dates(target, g["missing"]["dates"]),
                  "names": list(g["missing"]["names"])}
        jobs.append({"unit_id": u["unit_id"], "missed": missed, "messages": gapfill_messages(u, missed)})
    return jobs, skipped


def merge(responses, gapfill):
    """First-pass responses with the gap-fill facts appended (duplicates by type and value dropped)."""
    extra = {g["unit_id"]: g for g in gapfill if g.get("facts")}
    out, added = [], 0
    for r in responses:
        g = extra.get(r["unit_id"])
        if g and r.get("facts") is not None:
            have = {(f["type"], " ".join(f["value"].split()).lower()) for f in r["facts"]}
            new = [f for f in g["facts"] if (f["type"], " ".join(f["value"].split()).lower()) not in have]
            r = {**r, "facts": r["facts"] + new, "gapfill_added": len(new), "gapfill_model": g.get("model")}
            added += len(new)
        out.append(r)
    return out, {"units_with_gapfill": len(extra), "facts_added": added}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--responses", required=True)
    j.add_argument("--work", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trainset", "work"))
    j.add_argument("--out", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--responses", required=True)
    m.add_argument("--gapfill", required=True)
    m.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "jobs":
        units = _read(os.path.join(a.work, "sampled_train.jsonl")) + _read(os.path.join(a.work, "sampled_test.jsonl"))
        jobs, skipped = select(units, _read(a.responses))
        _write(a.out, jobs)
        print(f"{len(jobs)} gap-fill jobs -> {a.out}; not picked: {skipped}")
    else:
        rows, rep = merge(_read(a.responses), _read(a.gapfill))
        _write(a.out, rows)
        print(f"merged -> {a.out}: {rep}")


if __name__ == "__main__":
    main()
