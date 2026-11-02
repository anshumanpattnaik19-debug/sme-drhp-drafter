"""Stage 5: route facts to a section or sub-heading. BM25 over label, value and snippet, with a boost for
facts from the files the section needs. The same router builds the training inputs (PLAN.md 5.4)."""
from __future__ import annotations

import math
import re
from collections import Counter

TOP_K = 40
_TOK = re.compile(r"[a-z0-9]+")


def tokens(s: str) -> list[str]:
    return [t for t in _TOK.findall(s.lower()) if len(t) > 1]


def _doc(f):
    return tokens(f"{f['label']} {f['label']} {f['value']} {f.get('period', '')} {f.get('snippet', '')[:160]}")


def route(facts: list[dict], query: str, needs: list[str] | None = None, k: int = TOP_K,
          doc_types: dict | None = None) -> list[dict]:
    """facts: fact dicts with 'file_id'; doc_types: file_id -> doc_type, used for the needs boost."""
    if not facts:
        return []
    q = tokens(query)
    docs = [_doc(f) for f in facts]
    n = len(docs)
    avg = sum(len(d) for d in docs) / n or 1
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in set(q)}
    needs = set(needs or [])
    scored = []
    for f, d in zip(facts, docs):
        tf = Counter(d)
        s = sum(idf[t] * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / avg)) for t in q if t in tf)
        if doc_types and doc_types.get(f.get("file_id")) in needs:
            s = s * 1.5 + 1.0
        if f.get("origin") == "user":
            s += 2.0
        if f.get("reviewed"):
            s += 0.5
        if f.get("superseded"):
            s *= 0.2
        if s > 0:
            scored.append((s, f))
    scored.sort(key=lambda x: -x[0])
    return [f for _s, f in scored[:k]]
