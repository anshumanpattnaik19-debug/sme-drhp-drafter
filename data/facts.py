"""Typed facts (PLAN.md 5.2) and the three gates (5.3).

    fact = {"type": amount|percent|date|count|person|entity|place|short_text, "label", "value", "unit", "period"}
    normalise(raw_facts) -> (facts, schema_errors)
    apply_gates(facts, source, target, masked_values) -> (kept_facts, report)

precision: every value occurs in the source unit (numbers by value, dates by calendar date, text by tokens)
leakage:   a fact sharing an 8-word sequence with the target is dropped (the model must write, not copy)
masking:   facts carrying a value that DRHP-stage masking removed (price, issue size, offer dates) are dropped
coverage:  every figure and date in the target, and at least 90% of its proper names, are in the kept facts
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

TYPES = ("amount", "percent", "date", "count", "person", "entity", "place", "short_text")
TYPE_ALIASES = {"number": "count", "money": "amount", "currency": "amount", "percentage": "percent", "name": "person",
                "organisation": "entity", "organization": "entity", "company": "entity", "location": "place", "text": "short_text"}
NAME_COVERAGE_MIN = 0.9
LEAK_N = 8

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], start=1)}
MON = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
RE_DATES = [re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{MON},?\s+((?:19|20)\d{{2}})\b", re.I),
            re.compile(rf"\b{MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b", re.I),
            re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-]((?:19|20)\d{2})\b")]
# a number starts after a space, "₹" or "Rs." but not inside another number ("1,405.09" is one figure, not 405.09)
RE_FIG = re.compile(r"(?<![\w,])(?<!\d\.)\(?-?\d[\d,]*(?:\.\d+)?\)?%?(?![\w])")
RE_REF = re.compile(r"(page|pages|regulation|section|rule|rules|order|schedule|clause|article|chapter|annexure|note|form|item|"
                    r"sl\.?|sr\.?|no\.)s?\s*$", re.I)
STOPCAPS = set("""our the this that these those any each such all further however also in on of and for to a an as at by from with
company company's companies equity share shares board director directors promoter promoters group issue offer draft red herring prospectus
sebi icdr regulations regulation act rules india indian limited net proceeds fresh risk risks factor factors section sections annexure
restated financial information statements statement rs lakhs lakh crore crores page pages note notes total particulars details year years
date fy financial-year management business objects key internal external government approvals our-company registrar bse nse sme
emerge platform stock exchange exchanges market maker lead manager book running capital structure general information
ld reg sr no nos company's company’s pvt ltd
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
judge junior senior civil division court courts magistrate tribunal bench honourable hon'ble justice
bid opening closing""".split())


def _num(s):
    t = str(s).replace(",", "").replace("₹", "").strip().strip("()").rstrip("%")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def parse_dates(text):
    out = set()
    for rx in RE_DATES[:2]:
        for m in rx.finditer(text):
            g = m.groups()
            day, mon, yr = (g[0], g[1], g[2]) if g[0].isdigit() else (g[1], g[0], g[2])
            mi = MONTHS.get(mon.lower().rstrip(".")[:3] if len(mon) <= 4 else mon.lower(), None) or \
                next((v for k, v in MONTHS.items() if k.startswith(mon.lower().rstrip(".")[:3])), None)
            try:
                out.add(dt.date(int(yr), mi, int(day)))
            except (TypeError, ValueError):
                pass
    for m in RE_DATES[2].finditer(text):
        try:
            out.add(dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            pass
    return out


RE_FISCAL = re.compile(r"\b(?:FY\s?)?(?:19|20)\d{2}\s?[-–/]\s?\d{2,4}\b")
RE_PAGES = re.compile(r"\bpages?\s+\d+(?:\s*(?:,|and|&|to|-|–)\s*\d+)*", re.I)
# table-header dates: "31-Mar-23", "30-June-25", "01-Feb- 24"; "31, 2022" with the month lost; "March 31" with no year
RE_DATE_PARTS = [re.compile(rf"\b\d{{1,2}}\s?[-/ ]\s?{MON}\s?[-/ ]?\s?\d{{2,4}}\b", re.I),
                 re.compile(r"\b\d{1,2},\s?(?:19|20)\d{2}\b"),
                 re.compile(rf"\b{MON}\s+\d{{1,2}}(?:st|nd|rd|th)?\b", re.I)]


def _strip_dates(text):
    """Dates, parts of dates, fiscal years ("2009-10", "FY 2025-26") and page lists are not figures to cover."""
    for rx in RE_DATES + RE_DATE_PARTS:
        text = rx.sub(" ", text)
    text = RE_FISCAL.sub(" ", text)
    return RE_PAGES.sub(" ", text)


def figures(text):
    """Figures a target states and the facts must cover: not years, not page or legal references, not list numbers."""
    t = _strip_dates(text)
    out = set()
    ref_end = -1
    for m in RE_FIG.finditer(t):
        raw = m.group(0).strip("()").rstrip(",")
        k = _num(raw)
        if k is None:
            continue
        digits = raw.replace(",", "").replace(".", "").lstrip("-").rstrip("%")
        if "." not in raw and "," not in raw and not raw.endswith("%"):
            if len(digits) <= 1 or re.fullmatch(r"(19|20)\d{2}", digits):
                continue
        if RE_REF.search(t[max(0, m.start() - 14):m.start()]) or \
                (ref_end >= 0 and re.fullmatch(r"\s*(?:(?:,|and|&|to|or|/|-|–)\s*)?", t[ref_end:m.start()])):
            ref_end = m.end()                         # "Sections 197, 198 and 203": every number of the list
            continue
        ref_end = -1
        line_start = t.rfind("\n", 0, m.start()) + 1
        if re.fullmatch(r"\s*\(?", t[line_start:m.start()]) and re.match(r"\s*[.)]\s", t[m.end():m.end() + 2] or ""):
            continue                                  # "12. We depend on ..." numbering
        if m.group(0).endswith(")") and "(" not in m.group(0) and re.fullmatch(r"\d{1,3}", digits):
            continue                                  # "; 22) Considering ..." numbering inside a paragraph
        d0 = m.start() + re.search(r"\d", m.group(0)).start()
        if "." not in raw and len(digits) >= 4 and re.search(r"[A-Za-z]\w*\s?[-–]\s?$", t[max(0, d0 - 12):d0]):
            continue                                  # codes and PIN codes: "CTE- 88462", "i7-13700", "Siliguri-734005"
        out.add(abs(k))                               # facts carry no sign: "-6.9" and "(6.9)" are covered by 6.9
    return out


COMMON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trainset", "work", "common_words.json")
_COMMON = None
RE_ROMAN = re.compile(r"^[IVXLC]+$")


def common_words():
    """Words the corpus mostly writes in lower case ("drying", "court", "purposes"): capitalised, they start a sentence
    or a heading rather than name someone. Built by `data.build units` from the train split."""
    global _COMMON
    if _COMMON is None:
        try:
            with open(COMMON_PATH, encoding="utf-8") as fh:
                _COMMON = set(json.load(fh))
        except (OSError, ValueError):
            _COMMON = set()
    return _COMMON


def set_common_words(words):
    global _COMMON
    _COMMON = set(words)


def _name_like(tok):
    t = tok.strip(".,;:'’()\"“”-–")
    if not t or t.lower() in STOPCAPS or RE_ROMAN.match(t) or re.match(r"(?i)(no|sr|sl|s)\.", t):
        return False                      # "No.Nature" is a table header
    if t.isupper() or (len(t) > 2 and t.endswith("s") and t[:-1].isupper()):
        return False                      # acronyms are mostly terms (USD, CAGR, GST, IFRS), not names
    return t[:1].isupper() and t.lower() not in common_words()


def proper_names(text):
    """Proper names a target mentions, as tuples of their name-like tokens (common words dropped)."""
    names = set()
    runs = []
    text = re.sub(r"[“\"][^”\"\n]{1,80}[”\"]", " ", text)   # quoted titles and defined terms (“Our Business”, the “Defendant”)
    for m in re.finditer(r"(?:[A-Z][a-zA-Z'’.-]+|&)(?:\s+(?:[A-Z][a-zA-Z'’.-]+|&|of|and|de|da))*", text):
        # a flattened table runs names together: split at honorifics and relationship words
        runs += [p for p in re.split(r"\s(?=(?:Mr|Mrs|Ms|Dr|Shri|Smt|Late)\.?\s)|\s(?:Father|Mother|Wife|Husband|Brother|Sister|Son|Daughter|Spouse)\s",
                                     m.group(0)) if p]
    for run in runs:
        toks = [w for w in run.split() if w not in ("&", "of", "and", "de", "da")]
        toks = [w for w in toks if w.rstrip(".") not in ("Mr", "Mrs", "Ms", "Dr", "Shri", "Smt", "Late")][:6]
        core = [w.strip(".,;:'’()\"“”") for w in toks if _name_like(w)]
        if core and (len(core) >= 2 or len(toks) >= 2 or core[0].isupper()):
            names.add(" ".join(core))
    return names


def normalise(raw):
    facts, errors = [], []
    if isinstance(raw, dict):
        raw = raw.get("facts", [])
    for i, f in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(f, dict):
            errors.append(f"fact {i}: not an object")
            continue
        typ = str(f.get("type", "")).strip().lower()
        typ = TYPE_ALIASES.get(typ, typ)
        val = str(f.get("value", "")).strip()
        lab = str(f.get("label", "")).strip()
        if typ not in TYPES:
            errors.append(f"fact {i}: unknown type {typ!r}")
            continue
        if not val or not lab:
            errors.append(f"fact {i}: empty label or value")
            continue
        if typ == "short_text" and len(val.split()) > 12:
            val = " ".join(val.split()[:12])
            errors.append(f"fact {i}: short_text cut to 12 words")
        facts.append({"type": typ, "label": lab[:100], "value": val[:160], "unit": str(f.get("unit") or "").strip()[:30],
                      "period": str(f.get("period") or "").strip()[:40]})
    return facts, errors


def _tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def precise(f, source, src_nums, src_dates, src_tokens):
    v = f["value"]
    if len(v) >= 2 and " ".join(v.split()).lower() in " ".join(source.split()).lower():
        return True                       # verbatim, including numbers the PDF text broke ("11, 250")
    if f["type"] == "date":
        d = parse_dates(v)
        if d:
            return bool(d & src_dates)
    if f["type"] in ("amount", "percent", "count"):
        k = _num(re.sub(r"[^\d.,()-]", "", v) or v)
        if k is not None:
            return k in src_nums
    toks = _tokens(v)
    if not toks:
        return False
    if v.lower() in source.lower():
        return True
    return sum(t in src_tokens for t in toks) / len(toks) >= 0.8


def _words(s):
    """Words for the leakage check: numbers and codes are not prose."""
    return re.findall(r"[a-z]{2,}", s.lower())


def _ngrams(toks, n):
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def apply_gates(facts, source, target, masked_values=()):
    src_nums = {k for k in (_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", source)) if k is not None}
    src_dates = parse_dates(source)
    src_tokens = set(_tokens(source))
    masked = {k for k in (_num(x) for x in masked_values) if k is not None}
    tgt_grams = _ngrams(_words(target), LEAK_N)
    kept, dropped = [], {"imprecise": [], "leak": [], "masked": []}
    for f in facts:
        if not precise(f, source, src_nums, src_dates, src_tokens):
            dropped["imprecise"].append(f)
            continue
        k = _num(re.sub(r"[^\d.,()-]", "", f["value"])) if f["type"] in ("amount", "count") else None
        if (k is not None and k in masked and k not in figures(target)) or re.search(r"\b(issue|offer|floor|cap) price\b|price band|lot size|issue size|opening date|closing date",
                                                        f["label"], re.I):
            dropped["masked"].append(f)
            continue
        # leakage applies to free text only: names, places, identifiers and quoted titles must be copied verbatim
        quoted = re.search(r"[“\"']\s*" + re.escape(f["value"].strip()) + r"\s*[”\"']", source)
        if f["type"] == "short_text" and not quoted and len(_words(f["value"])) >= LEAK_N and _ngrams(_words(f["value"]), LEAK_N) & tgt_grams:
            dropped["leak"].append(f)
            continue
        kept.append(f)
    fact_text = " ".join(f"{f['value']}" for f in kept)
    fact_nums = {k for k in (_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", fact_text)) if k is not None}
    fact_dates = set().union(*[parse_dates(f["value"]) for f in kept]) if kept else set()
    need_nums = figures(target)
    need_dates = parse_dates(target)
    miss_nums = sorted(need_nums - fact_nums)
    miss_dates = sorted(str(d) for d in need_dates - fact_dates)
    names = proper_names(target)
    fact_toks = set(_tokens(fact_text + " " + " ".join(f["label"] for f in kept)))
    # a name is covered when every name-like token of it is in the facts ("Gadhethariya" in a person fact)
    miss_names = sorted(n for n in names if not set(_tokens(n)) <= fact_toks)
    name_cov = 1 - len(miss_names) / len(names) if names else 1.0
    n_teacher = len(facts)
    report = {
        "facts_in": n_teacher, "facts_kept": len(kept),
        "precision": round(1 - len(dropped["imprecise"]) / n_teacher, 3) if n_teacher else None,
        "dropped": {k: len(v) for k, v in dropped.items()},
        "coverage_figures": round(1 - len(miss_nums) / len(need_nums), 3) if need_nums else 1.0,
        "coverage_dates": round(1 - len(miss_dates) / len(need_dates), 3) if need_dates else 1.0,
        "coverage_names": round(name_cov, 3),
        "missing": {"figures": miss_nums[:20], "dates": miss_dates[:10], "names": miss_names[:10]},
        "n_missing": {"figures": len(miss_nums), "dates": len(miss_dates), "names": len(miss_names)},
    }
    report["pass"] = not miss_nums and not miss_dates and name_cov >= NAME_COVERAGE_MIN and bool(kept)
    return kept, report
