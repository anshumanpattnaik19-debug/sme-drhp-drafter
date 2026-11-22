"""Does the period/basis check (verify/claims.py) keep correct sentences and catch altered ones?

    python -m evaluate.claims_mutation workspace/c2fce2deb7/facts.json [more facts.json ...]

For every typed percentage or money fact with exactly one fiscal-year period and a single-year source, three sentences are
built from the fact itself and checked against ALL the facts of its project, as the app does:

  correct   "In FY 2025-26, the <label> was 61.27%."              must NOT be masked        (false positive if it is)
  shifted   the same sentence with the fiscal year moved by 2     must be masked             (miss if it is not)
  average   "On average over the last three years, <label> ..."   must be masked             (miss if it is not)

A shifted or average sentence is counted only when no other fact states the same number for that year or on that basis (the
check masks only when every piece of evidence contradicts the sentence, so a number that is also true for another year is
rightly left alone). Synthetic sentences test the mechanism; they say nothing about how often a model writes them.
"""
from __future__ import annotations

import json
import re
import sys

from verify.claims import _evidence, cues, fiscal_years, mask_period_claims
from verify.checks import num_key


def _label(f):
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)|[%:]", "", f.get("label", ""))).strip().lower()[:70]


def _fy_text(year):
    return f"FY {year - 1}-{str(year)[2:]}"


def run(paths):
    stats = {"correct": [0, 0], "shifted": [0, 0], "average": [0, 0]}      # [cases, masked]
    shown = {"correct": [], "shifted": [], "average": []}
    for path in paths:
        facts = json.load(open(path, encoding="utf-8"))
        facts = facts if isinstance(facts, list) else facts.get("facts", [])
        ev = _evidence(facts)
        seen = set()
        for f in facts:
            val = str(f.get("value", ""))
            pct = f.get("unit") == "%" or f.get("type") == "percent"
            money = str(f.get("unit", "")).startswith("₹")
            years = fiscal_years(str(f.get("period") or ""))
            if not (pct or money) or len(years) != 1 or num_key(val) is None or len(val) > 14 or not _label(f):
                continue
            year, k = next(iter(years)), num_key(val)
            if (f.get("label"), val, year) in seen:
                continue
            seen.add((f.get("label"), val, year))
            if any(c["multi"] or c["half"] for _, c in ev.get(k, [])):
                continue                                                   # the source itself speaks of an average or a half-year
            shown_val = f"{val}%" if pct else f"₹{val} lakhs"
            label = _label(f)
            correct = f"In {_fy_text(year)}, the {label} was {shown_val}."
            shifted = f"In {_fy_text(year + 2)}, the {label} was {shown_val}."
            average = f"On average over the last three years, the {label} was {shown_val}."
            stats["correct"][0] += 1
            out = mask_period_claims(correct, facts)[1]
            if out:
                stats["correct"][1] += 1
                shown["correct"].append(correct)
            if not any(year + 2 in c["fy"] for _, c in ev.get(k, [])):
                stats["shifted"][0] += 1
                if mask_period_claims(shifted, facts)[1]:
                    stats["shifted"][1] += 1
                else:
                    shown["shifted"].append(shifted)
            stats["average"][0] += 1
            if mask_period_claims(average, facts)[1]:
                stats["average"][1] += 1
            else:
                shown["average"].append(average)
    return stats, shown


if __name__ == "__main__":
    stats, shown = run(sys.argv[1:])
    c, s, a = stats["correct"], stats["shifted"], stats["average"]
    print(f"correct sentences wrongly masked : {c[1]} of {c[0]}")
    print(f"shifted fiscal year caught       : {s[1]} of {s[0]}")
    print(f"invented average caught          : {a[1]} of {a[0]}")
    for name in ("correct", "shifted", "average"):
        for t in shown[name][:6]:
            print(f"  [{name}] {t}")
