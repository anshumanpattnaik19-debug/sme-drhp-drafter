"""Checks run on every drafted section and on the whole project (the review pack).

    verify_section(sec, draft, facts, offer) -> {"ungrounded", "grounded", "placeholders", "checklist", "drhp_stage", "score"}
    mask_ungrounded(text, facts, offer, context) -> (text with every ungrounded value as [●], what was masked)
    review_pack(project, files, facts, drafts) -> {"issues": [...], "summary": {...}}

What is checked in prose: figures (comma groups, decimals, 3+ digits; years skipped), 1-2 digit numbers where they
state a fact (ages, years of experience, percentages, ₹ amounts, counts such as "10 personnel"), dates, licence and
registration numbers, address numbers (Plot, Sector, Survey ...), names after an honorific (Mr., Smt., ...), and
capitalised words that are neither generic offer-document vocabulary (verify/vocab.py) nor in the inputs (places,
organisations, products).
Page references ("beginning on page 200") are not figures: they are listed apart and become [●] at DRHP stage.
"""
from __future__ import annotations

import re
from collections import defaultdict

from data.facts import RE_DATES, parse_dates
from draft.outline import SECTIONS, SECTION_BY_KEY
from extract.rules import norm_value
from verify.vocab import generic_words

PH = "[●]"
# a figure is not part of a longer token such as a date (31.03.2024) or an identifier
RE_FIGURE = re.compile(r"(?<![A-Za-z0-9/.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+|\d{3,})(?![A-Za-z0-9/]|\.\d)")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")
RE_ANYNUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
RE_PAGE_REF = re.compile(r"\bpages?\s+(?:no\.?\s*)?\d+(?:\s*(?:,|and|&|to|-|–)\s*\d+)*", re.I)
# 1-2 digit numbers that state a fact: "aged 45", "15 years of experience", "12%", "₹ 5 lakhs"
COUNT_NOUNS = (r"personnel|employees|staff|workers|labou?rers|engineers|professionals|units|machines|branches|outlets|"
               r"stores|showrooms|warehouses|customers|clients|distributors|dealers|vendors|suppliers|directors|members|"
               r"shareholders|plants|factories|offices|locations|countries|states|cities|districts|projects|products|"
               r"vehicles|trucks|beds|rooms|acres|hectares|days|hours")
RE_SMALL = re.compile(r"(?:\baged?\s+(?:about\s+|of\s+)?|\bage\s+of\s+)(\d{1,2})\b"
                      r"|(?<![\w.,/])(\d{1,2}(?:\.\d+)?)(?=\s?%|\s*(?:years?|yrs\.?|months?)\b)"
                      r"|(?:₹|Rs\.?|INR)\s?(\d{1,2}(?:\.\d+)?)(?![\d,.])"
                      rf"|(?<![\w.,/])(\d{{1,2}})(?=\s+(?:(?:new|more|additional|skilled|full[- ]time)\s+)?(?:{COUNT_NOUNS})\b)", re.I)
# licence, registration and certificate numbers: a digit and a separator, such as EIC/1105/18/000299 or 10012022000123
RE_FY = re.compile(r"\bFY\s?(\d{4}|\d{2})(?:\s*(?:-|–|to)\s*(?:FY\s?)?(\d{4}|\d{2}))?(?!\d)", re.I)
RE_IDENT = re.compile(r"(?<![\w/-])(?=[A-Z0-9/-]*\d)(?:[A-Z0-9]+[/-]){1,}[A-Z0-9]+(?![\w/-])|\b(?=[A-Z]*\d)[A-Z0-9]{10,}\b")
# address numbers: "Plot No. 28/29", "Sector - 18", "Survey No. 112/1A"
RE_ADDR = re.compile(r"\b(?:Plot|Sector|Survey|Khasra|Gat|Ward|Door|Shop|Flat|House|Block|Gala|Unit)\s*(?:No\.?|Nos\.?)?\s*[-:.]?\s*"
                     r"(\d+[A-Z]?(?:\s*[/,&-]\s*\d+[A-Z]?)*)", re.I)
RE_DATE_SPACED = re.compile(r"\b(\d{1,2})\s+(?:st|nd|rd|th)\s+(January|February|March|April|May|June|July|August|September|"
                            r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?,?\s+((?:19|20)\d{2})\b", re.I)
# a run of Title-case words (acronyms are left alone): "Village Kandiveli", "Elk Grove", "Ddev Plastiks"
RE_CAP_RUN = re.compile(r"(?<![\w'’])[A-Z][a-z][a-zA-Z'’]*(?:[ -][A-Z][a-z][a-zA-Z'’]*)*")
RE_HON_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+((?:[A-Z][a-zA-Z'’-]+\.?)(?:\s+[A-Z][a-zA-Z'’-]+\.?){0,3})")
RE_NAME_STOP = re.compile(r"\s*\b(?:Father|Mother|Spouse|Wife|Husband|Brother|Sister|Son|Daughter|Mr|Mrs|Ms|Dr|Shri|Smt)\b")
RE_WORD = re.compile(r"\w+", re.U)
DRHP_STAGE = [
    (re.compile(r"price band of ₹\s?\d", re.I), "price band stated"),
    (re.compile(r"(?:offer|issue) price of ₹\s?\d", re.I), "offer price stated"),
    (re.compile(r"(?:offer|issue|floor|cap) price\D{0,30}₹\s?\d[\d,.]*\s+per equity share", re.I), "per-share offer price stated"),
    (re.compile(r"(?:bid|offer|issue) (?:opening|closing|opens|closes)[^.]{0,30}\d{1,2}\s+[A-Z][a-z]+\s+20\d{2}", re.I), "offer date stated"),
    (re.compile(r"lot size of \d", re.I), "lot size stated"),
]


def num_key(s):
    """1,860.00 / 1860 / 1860.0 / 56.00% compare equal; None for non-numbers."""
    t = str(s).replace(",", "").replace("₹", "").strip().rstrip("%").strip("()")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def _numbers(text):
    out = set()
    for x in RE_FIGURE.findall(str(text)):
        k = num_key(x)
        if k is not None:
            out.add(k)
    k = num_key(text)
    if k is not None:
        out.add(k)
    return out


def _any_numbers(text):
    """Every number in a fact value counts, small ones included ("45 years", "2 units")."""
    out = {num_key(x) for x in RE_ANYNUM.findall(str(text))}
    out.add(num_key(text))
    return out - {None}


def _offer_texts(offer):
    return [str(v) for v in (offer or {}).values() if isinstance(v, (str, int, float))]


def known_values(facts, offer, context=""):
    vals = set()
    for t in [f["value"] for f in facts] + _offer_texts(offer) + [context]:
        vals |= _any_numbers(t)
    return vals


class Known:
    """What the inputs support: numbers, dates and words of the facts, the offer terms and any context text (the
    company name, the section heading)."""

    def __init__(self, facts, offer=None, context=""):
        texts = [str(f["value"]) for f in facts] + _offer_texts(offer) + [context]
        self.numbers = known_values(facts, offer, context)
        self.dates = set().union(*(parse_dates(t) for t in texts)) if texts else set()
        self.words = {w.lower() for t in texts for w in RE_WORD.findall(t)}
        self.text = "\n".join(texts).lower()


def scan(text, known):
    """Values in a piece of prose, each {"kind", "start", "end", "raw", "grounded"}; kinds: figure, small, date, name,
    page_ref. Spans do not overlap: dates and page references are taken first, so their digits are not figures."""
    found, taken = [], []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    for rx in RE_DATES + [RE_DATE_SPACED]:
        for m in rx.finditer(text):
            if free(*m.span()):
                d = parse_dates(re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", m.group(0)))   # "27 th October" -> "27th October"
                found.append({"kind": "date", "start": m.start(), "end": m.end(), "raw": m.group(0),
                              "grounded": bool(d) and d <= known.dates})
                taken.append(m.span())
    for m in RE_PAGE_REF.finditer(text):
        if free(*m.span()):
            found.append({"kind": "page_ref", "start": m.start(), "end": m.end(), "raw": m.group(0), "grounded": False})
            taken.append(m.span())
    for m in RE_ADDR.finditer(text):                   # before identifiers: "Plot No. 28/29/36 / 37 / 38" is one address
        if free(*m.span(1)):
            nums = [num_key(x) for x in re.findall(r"\d+", m.group(1))]
            found.append({"kind": "address", "start": m.start(1), "end": m.end(1), "raw": m.group(1),
                          "grounded": all(k in known.numbers for k in nums)})
            taken.append(m.span(1))
    for m in RE_FY.finditer(text):                    # "FY2100 to FY2105" is not a period: the years must be consecutive
        g1, g2 = m.group(1), m.group(2)
        if not free(*m.span()) or (g2 is None and len(g1) == 2):      # "FY26" in a table header is left alone
            continue
        if g2 is not None and (int(g2[-2:]) - int(g1[-2:])) % 100 == 1 and (len(g1) != 4 or len(g2) != 4 or int(g2) - int(g1) == 1):
            continue                                                  # a fiscal period, as "FY 2023-24" is
        tok = re.sub(r"\s+", "", m.group(0)).lower()
        kt = re.sub(r"\s+", "", known.text)
        # the same period in the inputs may be written "FY2020 - FY2031P" (a projection) or "FY2020-21": the dash and
        # "to" are the same separator, and a trailing P marks a projection, so neither changes which years are meant
        pat = re.escape(tok.replace("to", "-").replace("–", "-")).replace(r"\-", "[-–]?(?:to)?")
        grounded = bool(re.search(pat + r"p?(?![a-z0-9])", kt.replace("–", "-"))) or tok in kt or (g2 is None and g1 in kt)
        found.append({"kind": "fiscal_year", "start": m.start(), "end": m.end(), "raw": m.group(0), "grounded": grounded})
        taken.append(m.span())
    for m in RE_IDENT.finditer(text):
        raw = m.group(0)
        if len(raw) < 6 or sum(c.isdigit() for c in raw) < 3:       # "COVID-19", "1-2 years", "B-2" are not identifiers
            continue
        if free(*m.span()) and not RE_YEAR.match(raw) and not re.fullmatch(r"(?:19|20)\d{2}\s*[-/]\s*\d{2,4}", raw):
            found.append({"kind": "identifier", "start": m.start(), "end": m.end(), "raw": raw,
                          "grounded": raw.lower() in known.text})        # FY "2023-24" is a period, not an identifier
            taken.append(m.span())
    for m in RE_FIGURE.finditer(text):
        raw, k = m.group(1), num_key(m.group(1))
        if k is None or RE_YEAR.match(raw) or not free(*m.span(1)):
            continue
        found.append({"kind": "figure", "start": m.start(1), "end": m.end(1), "raw": raw, "grounded": k in known.numbers})
        taken.append(m.span(1))
    for m in RE_SMALL.finditer(text):
        g = next(i for i in (1, 2, 3, 4) if m.group(i))
        if free(*m.span(g)):
            found.append({"kind": "small", "start": m.start(g), "end": m.end(g), "raw": m.group(g),
                          "grounded": num_key(m.group(g)) in known.numbers})
            taken.append(m.span(g))
    for m in RE_HON_NAME.finditer(text):
        # a flattened family table runs on: "Sandeep Dhurka Spouse’s ...", "Aanchal Sureka Brother Mr." -> the name only
        cut = RE_NAME_STOP.search(m.group(1))
        s, e = m.start(1), m.start(1) + (cut.start() if cut else len(m.group(1)))
        raw = text[s:e].rstrip(" .")
        e = s + len(raw)
        words = [w.lower() for w in RE_WORD.findall(raw)]
        if words and free(s, e):
            found.append({"kind": "name", "start": s, "end": e, "raw": raw, "grounded": all(w in known.words for w in words)})
            taken.append((s, e))
    generic = generic_words()
    for m in RE_CAP_RUN.finditer(text):               # places, organisations, products without an honorific
        rare = [w for w in re.finditer(r"[A-Za-z'’]+", m.group(0))
                if len(w.group(0)) > 2 and re.sub(r"['’]s?$", "", w.group(0)).lower() not in generic
                and re.sub(r"['’]s?$", "", w.group(0)).lower() not in known.words]
        if not rare:
            continue
        s, e = m.start() + rare[0].start(), m.start() + rare[-1].end()   # "Village Kandiveli" -> "Village [●]"
        if free(s, e):
            found.append({"kind": "name", "start": s, "end": e, "raw": text[s:e], "grounded": False})
            taken.append((s, e))
    return sorted(found, key=lambda f: f["start"])


def mask_ungrounded(text, facts, offer=None, context=""):
    """The text with every ungrounded figure, number, date and honorific name, and every page reference, replaced by
    [●]; returns (text, masked), masked being [{"kind", "raw", "context"}] for the reviewer."""
    known = Known(facts, offer, context)
    hits = [f for f in scan(text, known) if not f["grounded"]]
    masked = [{"kind": f["kind"], "raw": f["raw"], "context": text[max(0, f["start"] - 60):f["end"] + 40]} for f in hits]
    for f in reversed(hits):
        if f["kind"] == "page_ref":
            rep = re.sub(r"\d.*$", PH, f["raw"])          # "page 200" -> "page [●]"
        else:
            rep = PH
        text = text[:f["start"]] + rep + text[f["end"]:]
    return text, masked


def verify_section(key, draft, facts, offer):
    """Figures: 'in place' when the block's own cited facts or sources contain them (tables copied by code from a
    cited schedule count as in place); 'weak' when they only exist somewhere else in the inputs; else ungrounded.
    Checklist: 'covered' only when a builder produced the item; 'unconfirmed' when prose merely mentions it."""
    sec = SECTION_BY_KEY[key]
    kn = Known(facts, offer)
    known = kn.numbers
    offer_nums = known_values([], offer)
    by_id = {f["id"]: f for f in facts}
    in_place, weak, ungrounded, page_refs = 0, [], [], []
    prose, text_all = [], []
    for b in draft.get("blocks", []):
        if b["type"] == "brief":
            continue
        if b["type"] == "table":
            cells = [c for r in (b.get("rows") or [])[1:] for c in r[1:]]
            text_all.append(" ".join(cells))
            if b.get("sources"):
                in_place += sum(len(_numbers(c)) for c in cells)
                continue
            texts = cells
        else:
            text_all.append(b.get("text", ""))
            texts = [b.get("text", "")]
            if b["type"] == "paragraph":
                prose.append(b.get("text", ""))
        local = set(offer_nums)
        for fid in b.get("facts", []):
            if fid in by_id:
                local |= _numbers(by_id[fid]["value"])
        for s in b.get("sources", []):
            # a cited passage or schedule row: every number in it counts, small integers included
            local |= {k for k in (num_key(x) for x in RE_ANYNUM.findall(s.get("snippet", ""))) if k is not None}
        for t in texts:
            for f in scan(t, kn):
                ctx = t[max(0, f["start"] - 60):f["end"] + 40]
                if f["kind"] == "page_ref":
                    page_refs.append({"figure": f["raw"], "context": ctx})
                elif f["kind"] != "figure":           # small numbers, dates, names: against all the inputs
                    if not f["grounded"]:
                        ungrounded.append({"figure": f["raw"], "context": ctx, "kind": f["kind"]})
                elif num_key(f["raw"]) in local:
                    in_place += 1
                elif f["grounded"]:
                    weak.append({"figure": f["raw"], "context": ctx})
                else:
                    ungrounded.append({"figure": f["raw"], "context": ctx, "kind": "figure"})
    joined = "\n".join(text_all)
    low = "\n".join(prose).lower()
    covered = set(draft.get("covered") or [])
    checklist = []
    for item in sec["checklist"]:
        words = [w for w in re.findall(r"[a-z]+", item.lower()) if len(w) > 3]
        mentioned = bool(words) and sum(w[:6] in low for w in words) >= max(1, (len(words) + 1) // 2)
        status = "covered" if item in covered else "unconfirmed" if mentioned else "missing"
        checklist.append({"item": item, "status": status, "covered": status == "covered"})
    stage = [label for rx, label in DRHP_STAGE if rx.search(joined)]
    total = in_place + len(weak) + len(ungrounded)
    cov = sum(c["covered"] for c in checklist)
    return {"grounded": in_place, "weak": weak[:50], "ungrounded": ungrounded[:50],
            "grounding": round(in_place / total, 3) if total else None,
            "placeholders": joined.count("[●]"), "page_refs": page_refs[:50], "checklist": checklist,
            "checklist_coverage": round(cov / len(checklist), 3) if checklist else None, "drhp_stage": stage,
            "narrative_pending": len(draft.get("narrative_pending") or []),
            "missing_inputs": draft.get("missing") or []}


def _consistency(facts):
    """Same label, period and kind of number (a % column is not compared with a ₹ column), different values
    in different files. 58.1 and 58.10 are the same value."""
    groups = defaultdict(list)
    for f in facts:
        if f["type"] in ("amount", "percent", "count") and f.get("period") and not f.get("superseded"):
            per = f["period"].lower()
            kind = "pct" if f["type"] == "percent" or "%" in per else "lakhs" if "lakh" in per or "₹" in per else f["type"]
            key = (re.sub(r"[^a-z]", "", f["label"].lower()), re.sub(r"[^0-9]", "", per), kind)
            groups[key].append(f)
    out = []
    for _key, fs in groups.items():
        vals = {num_key(f["value"]) if num_key(f["value"]) is not None else norm_value(f["value"]) for f in fs}
        files = {f["file_id"] for f in fs}
        if len(vals) > 1 and len(files) > 1:
            out.append(fs)
    return out


def review_pack(project, files, facts, drafts):
    issues = []
    present = {f.get("doc_type") for f in files if f.get("status") == "processed"}
    for sec in SECTIONS:
        missing = [n for n in sec["needs"] if n not in present]
        if missing:
            issues.append({"severity": "high" if sec["writer"] in ("slm_core", "inserted") else "medium",
                           "kind": "missing_input", "section": sec["key"],
                           "title": f"Missing input for {sec['title']}",
                           "detail": "No file classified as: " + ", ".join(missing)})
    for f in files:
        if f.get("status") == "failed":
            issues.append({"severity": "high", "kind": "ingest", "file_id": f["id"], "title": f"Could not read {f['name']}",
                           "detail": f.get("error", "")})
        elif f.get("needs_ocr_pages"):
            issues.append({"severity": "medium", "kind": "ocr", "file_id": f["id"],
                           "title": f"{f['name']}: {f['needs_ocr_pages']} page(s) not OCR'd",
                           "detail": "Scanned pages carry no text yet. Enable OCR or raise the OCR page limit in Settings, then reprocess the file."})
    for fs in _consistency(facts)[:40]:
        vals = "; ".join(f"{f['value']} ({f.get('file_name', '')})" for f in fs[:4])
        issues.append({"severity": "medium", "kind": "inconsistency", "fact_ids": [f["id"] for f in fs],
                       "title": f"Inconsistent figure: {fs[0]['label']} · {fs[0]['period']}", "detail": vals})
    for key, d in (drafts or {}).items():
        v = d.get("verification") or {}
        sec = SECTION_BY_KEY.get(key, {"title": key, "writer": ""})
        title = sec["title"]
        core = sec["writer"] in ("slm_core", "code")
        if v.get("ungrounded"):
            issues.append({"severity": "high", "kind": "ungrounded", "section": key,
                           "title": f"{len(v['ungrounded'])} figure(s) in {title} not found in the inputs",
                           "detail": ", ".join(u["figure"] for u in v["ungrounded"][:8])})
        if v.get("weak"):
            issues.append({"severity": "medium", "kind": "weak", "section": key,
                           "title": f"{len(v['weak'])} figure(s) in {title} not traced to the cited source",
                           "detail": "Found elsewhere in the inputs but not in the facts or schedule this block cites: "
                                     + ", ".join(u["figure"] for u in v["weak"][:8])})
        for m in v.get("missing_inputs", []):
            issues.append({"severity": "high" if core else "medium", "kind": "missing_input", "section": key,
                           "title": f"{title}: {m['item']}", "detail": f"Not in the inputs. Request from the issuer: {m['where']}."})
        if v.get("narrative_pending"):
            issues.append({"severity": "medium", "kind": "narrative", "section": key,
                           "title": f"{title}: {v['narrative_pending']} sub-heading(s) need prose",
                           "detail": "Shown as drafting briefs. Connect the fine-tuned SLM in Settings, or write them in the editor."})
        for c in v.get("checklist", []):
            st = c.get("status", "covered" if c["covered"] else "missing")
            if st == "missing":
                issues.append({"severity": "medium", "kind": "checklist", "section": key,
                               "title": f"{title}: “{c['item']}” not covered", "detail": "Mandatory disclosure item missing from the draft."})
            elif st == "unconfirmed":
                issues.append({"severity": "low", "kind": "checklist", "section": key,
                               "title": f"{title}: “{c['item']}” to confirm", "detail": "Mentioned in prose; a reviewer must confirm the disclosure is complete."})
        for s in v.get("drhp_stage", []):
            issues.append({"severity": "high", "kind": "drhp_stage", "section": key, "title": f"{title}: {s}",
                           "detail": "At DRHP stage this must be [●]."})
    if "risk_factors" not in (drafts or {}):
        for f in facts:
            if f["type"] == "short_text" and re.search(r"\bexpired\b|\bnot obtained\b|\bobjected\b", f["value"], re.I):
                issues.append({"severity": "medium", "kind": "disclosure", "fact_ids": [f["id"]],
                               "title": f"Flag for risk factors: {f['label']} — {f['value']}",
                               "detail": f"{f.get('file_name', '')} · {f.get('loc', '')}"})
    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: order[i["severity"]])
    for i, it in enumerate(issues):
        it["id"] = f"iss{i + 1}"
    drafted = list(drafts or {})
    signed = [k for k, d in (drafts or {}).items() if (d.get("review") or {}).get("status") == "reviewed"]
    summary = {
        "sections_total": len(SECTIONS), "sections_drafted": len(drafted), "sections_signed_off": len(signed),
        "high": sum(i["severity"] == "high" for i in issues), "medium": sum(i["severity"] == "medium" for i in issues),
        "low": sum(i["severity"] == "low" for i in issues),
        "placeholders": sum((d.get("verification") or {}).get("placeholders", 0) for d in (drafts or {}).values()),
        "narrative_pending": sum((d.get("verification") or {}).get("narrative_pending", 0) for d in (drafts or {}).values()),
        "by_kind": {k: sum(i["kind"] == k for i in issues) for k in
                    ("missing_input", "ungrounded", "weak", "narrative", "checklist", "inconsistency", "drhp_stage", "ocr", "ingest", "disclosure")},
    }
    return {"issues": issues, "summary": summary}
