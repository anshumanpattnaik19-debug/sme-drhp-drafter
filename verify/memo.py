"""What the guard derives from a list of facts, kept while the same list is used.

A draft is guarded paragraph by paragraph, and each of several checks first reads every fact (the numbers, dates and words they
hold, the evidence for each figure). On a data room of 7,700 facts that was 1.3 s per paragraph, and a section took minutes on the
pod (22 Nov 2026). The facts of one sub-heading's draft are one list object, so a result is built once for it and reused for the
paragraphs of every draft of that sub-heading. One list is kept at a time; a list that changes length, or a different list, starts
afresh. The facts themselves are never changed while a draft is guarded.
"""
from __future__ import annotations

_slot = {"facts": None, "n": -1, "store": {}}


def memo(facts, name, build):
    """build() once per (facts list, name); the result is shared, so callers must not change it."""
    if _slot["facts"] is not facts or _slot["n"] != len(facts):
        _slot["facts"], _slot["n"], _slot["store"] = facts, len(facts), {}
    store = _slot["store"]
    if name not in store:
        store[name] = build()
    return store[name]


def clear():
    _slot["facts"], _slot["n"], _slot["store"] = None, -1, {}
