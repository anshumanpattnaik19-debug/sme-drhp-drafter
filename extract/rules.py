"""Rule-based typed-fact extractor (stand-in for SLM skill 1, same output schema).

    extract_facts(blocks, file_meta) -> [{"type", "label", "value", "unit", "period", "loc", "page", "snippet"}]

Types follow PLAN.md 5.2: amount | percent | date | count | person | entity | place | identifier | short_text.
Sources of facts, in order of reliability:
  1. Excel rows: a text label followed by numbers, periods taken from the nearest header row above.
  2. Two-column key/value rows (Word tables, "Label: value" lines).
  3. Regex over running text: identifiers (CIN, GSTIN, DIN, PAN), ₹ amounts and percentages with the
     words before them as the label.
"""
from __future__ import annotations

import re

MAX_FACTS_PER_FILE = 400

NUM = r"\(?-?\d{1,3}(?:,\d{2,3})*(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?"
RE_NUM_ONLY = re.compile(rf"^\s*(?:₹|rs\.?|inr)?\s*({NUM})\s*(%|lakhs?|crores?|cr|mn|million)?\s*$", re.I)
RE_PERIOD = re.compile(r"\b(?:FY\s?\d{2,4}(?:-\d{2,4})?|20\d{2}-\d{2}|(?:as\s+at|as\s+on)\s+[^|]{4,30}|"
                       r"(?:31|30)\s+(?:march|september|december|june)\s+20\d{2}|H1\s?FY\d{2,4}|"
                       r"six months ended[^|]{0,25}|20\d{2})\b", re.I)
RE_DATE = re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|"
                     r"September|October|November|December),?\s+(?:19|20)\d{2})\b", re.I)
RE_AMOUNT = re.compile(rf"(?:₹|Rs\.?|INR)\s*({NUM})\s*(lakhs?|crores?|cr\b|million|mn\b)?", re.I)
RE_PERCENT = re.compile(rf"({NUM})\s?%")
IDENTIFIERS = {
    "CIN": re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}(?:PLC|PTC|FLC|GOI|NPL|SGC)\d{6}\b"),
    "GSTIN": re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b"),
    "DIN": re.compile(r"\bDIN[:\s-]*(\d{8})\b"),
    "FRN": re.compile(r"\bFRN[:\s.-]*(\d{6}[A-Z]?)\b", re.I),
}
RE_PERSON = re.compile(r"^(?:Mr\.?|Ms\.?|Mrs\.?|Shri|Smt\.?|Dr\.?|CA|CS)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}$")
RE_ENTITY = re.compile(r"\b(?:Limited|Ltd\.?|LLP|Private Limited|Pvt\.? Ltd\.?|Bank|Trust)\s*$")
RE_NUMBERED = re.compile(r"^\s*\d{1,2}(\.\d+)*\.?\s+[A-Z]")
STOP_LABELS = {"total", "particulars", "sr", "sr.", "no", "no.", "s.no", "#", "", "sl", "note", "notes"}


def _clean_num(s: str) -> float | None:
    neg = s.strip().startswith("(") and s.strip().endswith(")")
    t = s.replace(",", "").replace("(", "").replace(")", "").strip()
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def infer_type(value: str) -> tuple[str, str, str]:
    """(type, normalised value, unit) for a raw cell or value string."""
    v = value.strip()
    m = RE_NUM_ONLY.match(v)
    if m:
        unit = (m.group(2) or "").lower()
        if unit == "%":
            return "percent", m.group(1), "%"
        if unit:
            return "amount", m.group(1), "₹ crore" if unit.startswith("cr") else f"₹ {unit.rstrip('s')}s" if unit.startswith("lakh") else unit
        if re.match(r"^\(?-?\d+\)?$", m.group(1).replace(",", "")) and "." not in m.group(1):
            return "count", m.group(1), ""
        return "amount", m.group(1), ""
    if RE_DATE.fullmatch(v):
        return "date", v, ""
    for name, rx in IDENTIFIERS.items():
        if rx.fullmatch(v):
            return "identifier", v, name
    if RE_PERSON.match(v):
        return "person", v, ""
    if RE_ENTITY.search(v) and len(v.split()) <= 10:
        return "entity", v, ""
    return "short_text", " ".join(v.split()[:12]), ""


def _label(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" :-|.")
    return s[:90]


def _unit_hint(blocks) -> str:
    for b in blocks[:8]:
        t = b["text"].lower()
        if "₹ in lakhs" in t or "rs in lakhs" in t or "(₹ lakhs)" in t or "in lakhs" in t:
            return "₹ lakhs"
        if "in crore" in t:
            return "₹ crore"
    return ""


HEADER_FIRST = {"particulars", "sr", "sr.", "sr. no.", "#", "s.no", "s. no.", "name", "sl. no.", "no.", "item"}


def _is_header(cells, have_header):
    nonempty = [c for c in cells if c]
    if len(nonempty) < 2:
        return False
    plain_nums = [c for c in nonempty if RE_NUM_ONLY.match(c) and not RE_PERIOD.search(c)]
    if plain_nums:
        return False
    periods = sum(1 for c in nonempty if RE_PERIOD.search(c) and len(c) < 40)
    if periods >= 2 or nonempty[0].lower() in HEADER_FIRST:
        return True
    return not have_header and len(nonempty) >= 3 and all(len(c) < 40 for c in nonempty)


def _from_rows(blocks):
    """Excel: a row label followed by values; columns named by the latest header row on the same sheet.
    A header column that is a period (FY 2025-26, as at 30 September 2026) becomes the fact's period."""
    out, header, sheet, unit = [], None, None, ""
    for b in blocks:
        if b.get("sheet") != sheet:
            sheet, header = b.get("sheet"), None
            unit = _unit_hint([x for x in blocks if x.get("sheet") == sheet])
        cells = [c.strip() for c in b["text"].split(" | ")]
        if _is_header(cells, header is not None):
            header = cells
            continue
        lab_idx = next((i for i, c in enumerate(cells) if c and not RE_NUM_ONLY.match(c)), None)
        if lab_idx is None:
            continue
        lab = _label(cells[lab_idx])
        if lab.lower() in STOP_LABELS or len(lab) < 3:
            continue
        emitted = 0
        for i, c in enumerate(cells):
            if i <= lab_idx or not c or c == cells[lab_idx] or emitted >= 8:
                continue
            col = header[i] if header and i < len(header) else ""
            is_period = bool(col and RE_PERIOD.search(col) and len(col) < 40)
            typ, val, u = infer_type(c)
            if typ == "count" and unit:
                typ = "amount"
            if typ in ("amount", "count") and "%" in f"{lab} {col}":
                typ, u = "percent", "%"
            if typ == "short_text" and not col:
                continue
            out.append({"type": typ, "label": lab if (is_period or not col) else f"{lab} — {_label(col)}",
                        "value": val, "unit": u or (unit if typ == "amount" else ""),
                        "period": col if is_period else "",
                        "loc": b["loc"], "page": b.get("page"), "snippet": b["text"][:240]})
            emitted += 1
    return out


def _from_kv(blocks):
    out = []
    for b in blocks:
        lines = b["text"].split("\n")
        for ln in lines:
            parts = [p.strip() for p in ln.split(" | ")] if " | " in ln else None
            if parts and len(parts) == 2:
                k, v = parts
            elif parts and len(parts) == 3 and re.match(r"^\d+\.?$|^[a-z]\)$", parts[0]):
                k, v = parts[1], parts[2]
            else:
                m = re.match(r"^([A-Z][^:]{2,60}):\s+(.{1,120})$", ln.strip())
                if not m:
                    continue
                k, v = m.group(1), m.group(2)
            k = _label(k)
            if not v or k.lower() in STOP_LABELS or len(k) < 3 or len(v) > 160:
                continue
            if RE_NUMBERED.match(k) and RE_NUMBERED.match(v):
                continue                       # a two-column table of contents, not a fact
            typ, val, u = infer_type(v)
            out.append({"type": typ, "label": k, "value": val, "unit": u, "period": "",
                        "loc": b["loc"], "page": b.get("page"), "snippet": ln[:240]})
    return out


def _context_label(text, start, words=7):
    before = re.sub(r"\s+", " ", text[max(0, start - 140):start])
    toks = re.findall(r"[A-Za-z][A-Za-z&'/-]*", before)
    return _label(" ".join(toks[-words:])) or "Amount"


def _from_text(blocks):
    out = []
    for b in blocks:
        if b["kind"] == "row":
            continue
        t = b["text"]
        for name, rx in IDENTIFIERS.items():
            for m in rx.finditer(t):
                val = m.group(1) if rx.groups else m.group(0)
                out.append({"type": "identifier", "label": name, "value": val, "unit": name, "period": "",
                            "loc": b["loc"], "page": b.get("page"), "snippet": t[max(0, m.start() - 80):m.end() + 80]})
        for m in RE_AMOUNT.finditer(t):
            unit = (m.group(2) or "").lower()
            unit = "₹ crore" if unit.startswith("cr") else "₹ lakhs" if unit.startswith("lakh") else ("₹ " + unit if unit else "₹")
            out.append({"type": "amount", "label": _context_label(t, m.start()), "value": m.group(1), "unit": unit,
                        "period": "", "loc": b["loc"], "page": b.get("page"),
                        "snippet": t[max(0, m.start() - 100):m.end() + 60]})
        for m in RE_PERCENT.finditer(t):
            out.append({"type": "percent", "label": _context_label(t, m.start()), "value": m.group(1), "unit": "%",
                        "period": "", "loc": b["loc"], "page": b.get("page"),
                        "snippet": t[max(0, m.start() - 100):m.end() + 60]})
        for m in RE_DATE.finditer(t):
            out.append({"type": "date", "label": _context_label(t, m.start(), 6), "value": m.group(1), "unit": "",
                        "period": "", "loc": b["loc"], "page": b.get("page"),
                        "snippet": t[max(0, m.start() - 100):m.end() + 40]})
    return out


def norm_value(v: str) -> str:
    return re.sub(r"[\s,₹]|rs\.?", "", str(v).lower()).strip("()")


def _table_rows(blocks):
    """Word tables with three or more columns are read like a sheet: header row, then labelled rows."""
    out = []
    for b in blocks:
        if b["kind"] != "table":
            continue
        rows = b["text"].split("\n")
        if _ncols(b) < 3:
            continue
        for i, r in enumerate(rows, start=1):
            out.append({"page": b.get("page"), "loc": f"{b['loc']}, row {i}", "kind": "row", "text": r, "sheet": b["loc"]})
    return out


def _ncols(b):
    return max(len(r.split(" | ")) for r in b["text"].split("\n"))


def extract_facts(blocks: list[dict]) -> list[dict]:
    two_col = [b for b in blocks if b["kind"] != "table" or _ncols(b) < 3]
    facts = _from_rows([b for b in blocks if b["kind"] == "row"] + _table_rows(blocks)) + _from_kv(two_col) + _from_text(blocks)
    seen, out = set(), []
    for f in facts:
        f["snippet"] = re.sub(r"\s+", " ", f["snippet"]).strip()
        if f["type"] == "short_text" and len(f["value"]) < 2:
            continue
        key = (f["label"].lower(), norm_value(f["value"]), f["period"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
        if len(out) >= MAX_FACTS_PER_FILE:
            break
    return out
