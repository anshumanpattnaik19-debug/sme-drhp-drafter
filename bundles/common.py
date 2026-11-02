"""Formatting helpers and constants shared by all renderers."""
from __future__ import annotations

SYNTHETIC_MARK = "SYNTHETIC TEST DOCUMENT"
SYNTHETIC_FOOTER = ("Synthetic specimen generated for model testing. Fictitious company; "
                    "all names, identifiers and figures are invented.")


def _group_indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def inr(x, dp: int = 2, paren: bool = True, dash_zero: bool = True) -> str:
    """Indian digit grouping: 1,23,456.78; negatives in parentheses; zero as '-'."""
    if x is None:
        return "[●]"
    if dash_zero and abs(x) < 0.005:
        return "-"
    neg = x < 0
    v = abs(x)
    whole = int(v)
    frac = round(v - whole, dp)
    if frac >= 1:
        whole += 1
        frac = 0.0
    body = _group_indian(whole)
    if dp:
        body += "." + f"{frac:.{dp}f}"[2:]
    if neg:
        return f"({body})" if paren else f"-{body}"
    return body


def num(n: int) -> str:
    """Share counts: 1,00,00,000."""
    return _group_indian(int(n))


def pct(x, dp: int = 2) -> str:
    return "-" if x is None else f"{x:.{dp}f}%"


def words_lakh(x: float) -> str:
    return f"₹ {inr(x)} lakhs"
