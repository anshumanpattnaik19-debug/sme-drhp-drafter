"""Computed and not-yet-known ratio facts, so the model does not calculate.

    derive_facts(facts, sub, section_title) -> [fact dicts, origin "computed" or "unknown"]

19 Nov 2026 trace: 16% of the shipped model's invented figures were percentages and amounts it worked out itself ("approximately
0.96% of the Gross Proceeds", "up to ₹ 37.80 Lakhs"). Filed offer documents state such ratios, so the model learned to produce
them. Two kinds of fact stop that:

* computed: when the amount facts of a schedule add up to the schedule's own total (within 1%), each line's share of that total
  is computed here with the formula kept in the fact, and the model is given the answer. A set of amounts that does not add up
  is left alone: a wrong computed value is worse than a masked one.
* unknown: at DRHP stage the offer size and the gross proceeds are not fixed (data/mask.py turns them into [●]), so any ratio to
  them is [●] too. The facts say so, and the model copies the placeholder.
"""
from __future__ import annotations

import re

PH = "[●]"
RE_TOTAL = re.compile(r"^\s*(?:total|aggregate|sum)\b|\b(?:total|aggregate)\s+(?:estimated\s+)?(?:offer\s+)?(?:expenses|cost|project cost|funds?)\b", re.I)
RE_RATIO_SUB = re.compile(r"offer expenses|issue expenses|expenses of the (?:offer|issue)|objects? of the|gross proceeds|net proceeds|"
                          r"issue size|offer size|means of finance|utili[sz]ation|deployment", re.I)
TOLERANCE = 0.01


def _num(v):
    t = re.sub(r"[₹,\s]|Rs\.?", "", str(v)).rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def computed_shares(facts):
    """Shares of a total for amount facts whose lines add up to that total. [{label, value, formula}]"""
    amts = [(f, _num(f.get("value"))) for f in facts if f.get("type") == "amount" and not str(f.get("value", "")).startswith("[")]
    amts = [(f, v) for f, v in amts if v is not None and v > 0]
    totals = [(f, v) for f, v in amts if RE_TOTAL.search(str(f.get("label", "")))]
    out = []
    for tf, tv in totals:
        unit = tf.get("unit", "")
        lines = [(f, v) for f, v in amts if f is not tf and (f.get("unit", "") == unit) and not RE_TOTAL.search(str(f.get("label", ""))) and v < tv]
        if len(lines) < 2 or abs(sum(v for _, v in lines) - tv) > TOLERANCE * tv:
            continue
        for f, v in lines:
            share = round(v / tv * 100, 2)
            out.append({"label": f"{f['label']} as % of {tf['label']}", "value": f"{share:.2f}", "unit": "%",
                        "formula": f"{v:g} / {tv:g} x 100"})
    return out


def derive_facts(facts, sub, section_title=""):
    out = []
    for i, c in enumerate(computed_shares(facts)):
        out.append({"id": f"d{i}", "type": "percent", "label": c["label"], "value": c["value"], "unit": "%", "origin": "computed",
                    "formula": c["formula"]})
    if RE_RATIO_SUB.search(f"{sub} {section_title}"):
        have = " ".join(str(f.get("label", "")).lower() for f in facts)
        for label in ("offer expenses as % of gross proceeds", "offer expenses as % of offer size", "gross proceeds of the Offer"):
            key = "gross proceeds" if "gross" in label else "offer size"
            if key in have:
                continue                                       # the files do give it: nothing to add
            out.append({"id": f"d{len(out)}", "type": "short_text", "label": label, "value": PH, "origin": "unknown"})
    return out
