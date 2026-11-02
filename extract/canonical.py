"""Current vs superseded values. An issuer bundle carries history (the private-company CIN, a former name,
an earlier capital figure); the draft must use the value in force.

    mark_superseded(facts) -> facts   sets "superseded": True on values replaced by a later one
    current(facts, label=..., unit=...) -> fact | None
"""
from __future__ import annotations

import re

RE_FORMER = re.compile(r"\b(former|erstwhile|earlier|old|previous|prior to conversion)\b", re.I)


def mark_superseded(facts):
    cins = [f for f in facts if f.get("unit") == "CIN" or (f["type"] == "identifier" and f["label"] == "CIN")]
    # a public company's CIN (…PLC…) replaces the private company's (…PTC…) on conversion
    if any("PLC" in f["value"] for f in cins):
        for f in cins:
            if "PTC" in f["value"] and f["value"].replace("PTC", "PLC") in {g["value"] for g in cins}:
                f["superseded"] = True
    for f in facts:
        if f["type"] in ("identifier", "entity", "short_text") and RE_FORMER.search(f.get("label", "")):
            f["superseded"] = True
    return facts


def current(facts, label=None, unit=None, contains=None):
    for f in facts:
        if f.get("superseded"):
            continue
        if label and f["label"].lower() != label.lower():
            continue
        if unit and f.get("unit") != unit:
            continue
        if contains and contains.lower() not in f["label"].lower():
            continue
        return f
    return None
