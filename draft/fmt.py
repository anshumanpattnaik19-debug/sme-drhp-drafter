"""Offer-document number formats: Indian digit grouping, ₹ lakhs to 2 decimals, negatives in brackets."""
from __future__ import annotations

import re

RE_NUM = re.compile(r"^\(?(-?)\s*([\d,]+(?:\.\d+)?)\)?$")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")


def group(n: int) -> str:
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + parts) + "," + tail
    return s


def parse(v: str) -> float | None:
    m = RE_NUM.match(str(v).strip())
    if not m:
        return None
    x = float(m.group(2).replace(",", ""))
    neg = m.group(1) == "-" or str(v).strip().startswith("(")
    return -x if neg else x


def lakhs(v) -> str:
    x = v if isinstance(v, (int, float)) else parse(v)
    if x is None:
        return str(v)
    if abs(x) < 0.005:
        return "-"
    whole = int(round(abs(x) * 100)) // 100
    frac = int(round(abs(x) * 100)) % 100
    s = f"{group(whole)}.{frac:02d}"
    return f"({s})" if x < 0 else s


def shares(v) -> str:
    x = v if isinstance(v, (int, float)) else parse(v)
    if x is None:
        return str(v)
    return ("(" + group(x) + ")") if x < 0 else group(x)


def rupees(v) -> str:
    """Per-share prices keep 2 decimals; large rupee amounts are grouped without decimals."""
    x = v if isinstance(v, (int, float)) else parse(v)
    if x is None:
        return str(v)
    if abs(x) >= 1000 and float(x).is_integer():
        return shares(x)
    return lakhs(x)


def pct(v) -> str:
    s = str(v).strip()
    if s.endswith("%"):
        x = parse(s[:-1])
        return f"{x:.2f}%" if x is not None else s
    x = parse(s)
    return f"{x:.2f}%" if x is not None else s


def column_kind(header: str) -> str:
    h = header.lower()
    if "%" in h or "share of" in h or h.strip() in ("share", "margin"):
        return "pct"
    if re.search(r"\byear\b|date|month|period|valid|since|joined|age\b|class|din|no\.$|number$", h) and "number of" not in h:
        return "text"
    if "lakh" in h:
        return "lakhs"
    if re.search(r"shares|no\. of|number of|quantity|nos\.", h):
        return "shares"
    if "₹" in h or "price" in h or "cost" in h or "amount" in h:
        return "rupees"
    return "auto"


def cell(v: str, kind: str = "auto", table_unit: str = "") -> str:
    s = str(v).strip()
    if not s or s in ("-", "–", "[●]") or kind == "text":
        return s
    if s.endswith("%"):
        return pct(s)
    x = parse(s)
    if x is None:
        return s
    if kind == "pct":
        return pct(s)
    if kind == "lakhs" or (kind == "auto" and table_unit == "lakhs"):
        return lakhs(x)
    if kind == "shares":
        return shares(x)
    if kind == "rupees":
        return rupees(x)
    if RE_YEAR.match(s):
        return s
    if "." in s:
        return lakhs(x) if abs(x) >= 1 else f"{x:.2f}"
    return shares(x) if abs(x) >= 1000 else s
