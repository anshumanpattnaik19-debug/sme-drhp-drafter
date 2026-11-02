"""DRHP-stage masking (PLAN.md section 2): the targets are final prospectuses, so everything that is only known
after pricing becomes [●] — offer price and price band, issue size and proceeds in rupees, offer dates, lot
size — and "Prospectus" becomes "Draft Red Herring Prospectus".

    mask(text) -> (masked_text, masked_values)    masked_values: the numbers removed, to drop matching facts
"""
from __future__ import annotations

import re

PH = "[●]"
AMT = r"(?<![A-Za-z])(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?(?:\s?/-)?"
UNIT = r"(?:\s*(?:lakhs?|lacs?|crores?|cr\.?|million|mn))?"
DATE = (r"(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+20\d{2}"
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2})")

RULES = [
    # price band / offer price / issue price, with or without "per equity share"
    (re.compile(rf"(price band of\s*){AMT}(\s*(?:to|-|–)\s*){AMT}", re.I), lambda m: f"{m.group(1)}₹ {PH}{m.group(2)}₹ {PH}"),
    (re.compile(rf"((?:offer|issue|floor|cap|cut-off|anchor investor (?:offer|issue)) price\s*(?:of|is|:|at)?\s*){AMT}", re.I),
     lambda m: f"{m.group(1)}₹ {PH}"),
    (re.compile(rf"{AMT}(\s*(?:\(including a (?:share )?premium of\s*{AMT}\)\s*)?per (?:equity )?share)", re.I),
     lambda m: f"₹ {PH} per Equity Share"),
    (re.compile(rf"(at a premium of\s*){AMT}", re.I), lambda m: f"{m.group(1)}₹ {PH}"),
    # issue size and proceeds in rupees
    (re.compile(rf"(aggregating(?: up to)?(?: to)?\s*){AMT}{UNIT}", re.I), lambda m: f"{m.group(1)}₹ {PH} lakhs"),
    (re.compile(rf"((?:gross|net) (?:issue )?proceeds[^.\n]{{0,60}}?){AMT}{UNIT}", re.I), lambda m: f"{m.group(1)}₹ {PH}"),
    (re.compile(rf"(issue size[^.\n]{{0,40}}?){AMT}{UNIT}", re.I), lambda m: f"{m.group(1)}₹ {PH}"),
    # offer dates
    (re.compile(rf"((?:bid|issue|offer)\s*(?:/\s*(?:bid|issue|offer)\s*)?(?:opening|closing|opens|closes|period)(?: date)?[^.\n]{{0,25}}?){DATE}", re.I),
     lambda m: f"{m.group(1)}{PH}"),
    (re.compile(rf"((?:date of (?:allotment|listing)|listing date|allotment date)[^.\n]{{0,20}}?){DATE}", re.I), lambda m: f"{m.group(1)}{PH}"),
    # lot size and minimum application
    (re.compile(r"((?:market )?lot (?:size )?of\s*)[\d,]+(\s*equity shares)", re.I), lambda m: f"{m.group(1)}{PH}{m.group(2)}"),
    (re.compile(r"(minimum (?:application|bid)(?: size)?(?: of| is)?\s*)[\d,]+(\s*equity shares)", re.I), lambda m: f"{m.group(1)}{PH}{m.group(2)}"),
    # the document itself
    (re.compile(r"\b(?:Red Herring Prospectus|Prospectus)\b"), lambda m: "Draft Red Herring Prospectus"),
]
RE_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _lines_with_proceeds(text):
    """Table rows of gross/net proceeds and issue expenses carry price-dependent amounts: mask their numbers.
    Only rows that start with those labels; the per-object amounts in prose are known at DRHP stage."""
    out = []
    row = re.compile(r"^\s*(?:less:?\s*)?(?:\(?[a-z0-9]{1,3}[.)]\s*)?(?:gross proceeds|net proceeds|(?:estimated )?(?:issue|offer)"
                     r"(?: related)? expenses|total issue size)", re.I)
    for ln in text.split("\n"):
        if row.match(ln):
            ln = re.sub(r"(?<![\w.])\d[\d,]*\.\d+(?![\w.])|(?<![\w.])\d{1,3}(?:,\d{2,3})+(?![\w.])", PH, ln)
        out.append(ln)
    return "\n".join(out)


RE_EXPENSE_TABLE = re.compile(r"%\s*of\s*(?:the\s*)?total\s*(?:issue|offer)\s*size|(?:issue|offer)\s*(?:related\s*)?expenses?.{0,80}"
                              r"(?:particulars|amount)", re.I | re.S)


def _expense_tables(text):
    """The break-up of issue expenses (amounts, % of expenses, % of issue size) is price-dependent: every decimal
    figure in a paragraph that carries that table becomes [●]."""
    paras = re.split(r"(\n\s*\n)", text)
    for i, p in enumerate(paras):
        if RE_EXPENSE_TABLE.search(p):
            paras[i] = re.sub(r"(?<![\w.])\d[\d,]*\.\d+(?![\w])", PH, p)
    return "".join(paras)


def mask(text):
    removed = []
    before_tables = set(RE_NUM.findall(text))
    text = _expense_tables(text)
    removed += list(before_tables - set(RE_NUM.findall(text)))
    for rx, rep in RULES:
        def sub(m, rep=rep):
            removed.extend(RE_NUM.findall(m.group(0)))
            return rep(m)
        text = rx.sub(sub, text)
    before = set(RE_NUM.findall(text))
    text = _lines_with_proceeds(text)
    removed += list(before - set(RE_NUM.findall(text)))
    # a price-dependent amount masked in one place is masked wherever else it appears (not percentages)
    for v in sorted({r for r in removed if len(r.replace(",", "").replace(".", "")) >= 3}, key=len, reverse=True):
        text = re.sub(rf"(?<![\d,.]){re.escape(v)}(?![\d,]|\.\d|\s?%)", PH, text)
    text = re.sub(r"Draft Red Herring Prospectus(\s+Draft Red Herring Prospectus)+", "Draft Red Herring Prospectus", text)
    text = text.replace("Draft Draft Red Herring", "Draft Red Herring")
    return text, sorted({r for r in removed if len(r.replace(",", "")) >= 2})
