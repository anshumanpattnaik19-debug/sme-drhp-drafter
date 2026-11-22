"""Does a figure keep the period and the basis it has in its source?

mask_ungrounded (verify/checks.py) asks whether a value is in the inputs. This module asks what the draft says the value is
FOR. Hosted test of 20 Nov 2026: the draft wrote "top ten customers contribute about 61% of revenue on average over the last
three years ended FY 2025-26"; the files give 61.27% for FY 2025-26 alone and a rounded "about 61%" without a period. The value
was in the inputs, so nothing masked it; the period was the model's own.

Scope, kept narrow so that what it masks is right: percentages and money amounts in prose (never tables). Ages, face values,
capacities, pin codes and the like are not read as claims about a period.

A claim is checked against the evidence for the same number: typed facts (label, snippet, period) and the sentences of
passages that hold it. It is masked as [●] only when EVERY piece of evidence contradicts what the clause says, so a number that
the inputs give for two different things is never masked for the wrong one of them:

  * basis: an average or multi-year basis ("on average", "over the last three years", CAGR) that no evidence states. It binds
    only a figure within 90 characters of the cue, in a clause that names no more than one fiscal year (a clause listing
    "₹710.04 lakh for FY 2024 and ₹323.46 lakh for FY 2023" is a per-year list, not an average);
  * fiscal year: the year the figure is stated for ("... for FY 2024", else the clause's years) against the years the
    evidence names; and a half-year or quarter figure against a full-year one.

Evidence silent about its period neither supports nor contradicts a fiscal year named in the clause (many facts carry no
period); it does contradict an average or multi-year basis, which a source states whenever it means it.
Not checked: what a value is of, beyond "N% of X" (verify.checks.mask_misbased_percents); claims with no matching evidence at
all (mask_ungrounded masks those); a period the draft leaves out.
"""
from __future__ import annotations

import re

from verify.checks import PH, RE_ANYNUM, num_key

_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_PFX = r"(?:FY|F\.Y\.|fiscal(?: year)?|financial year)"
# "FY 2025-26", "FY2025-26", "FY 2026", "FY26", "fiscal 2026", "2025-26": all name the year ending March of the last one
RE_FY_RANGE = re.compile(rf"\b{_PFX}\s*'?(20\d{{2}})\s*[-–/]\s*(\d{{2}}|20\d{{2}})\b|\b(20\d{{2}})\s*[-–]\s*(\d{{2}})\b", re.I)
RE_FY_SINGLE = re.compile(rf"\b{_PFX}\s*'?(20\d{{2}}|\d{{2}})\b(?!\s*[-–/]\s*\d)", re.I)
RE_HALF = re.compile(r"\b(?:six|6)[- ]months?\b|\bH[12]\b|\bhalf[- ]year(?:ly)?\b|\bnine[- ]months?\b|\b9M\b|\bquarter(?:ly)?\b|\bQ[1-4]\b",
                     re.I)
RE_MULTI = re.compile(r"\bon average\b|\baverag(?:e|ed|es|ing)\b|\bCAGR\b|\bcompound annual\b|\bannuali[sz]ed\b"
                      r"|\b(?:last|past|preceding|previous|trailing)\s+(?:two|three|four|five|six|seven|eight|nine|ten|few|\d+)\s+"
                      r"(?:financial\s+|fiscal\s+)?years\b"                                  # "last three years", not "previous year"
                      r"|\b(?:two|three|four|five|six|seven|\d+)-year\s+(?:CAGR|average|period|trend|growth|history|track|data)\b"
                      r"|\bover (?:the )?(?:years|period)\b",
                      re.I)
RE_AVG = re.compile(r"\bon average\b|\baverag(?:e|ed|es|ing)\b|\bCAGR\b|\bcompound annual\b|\bannuali[sz]ed\b", re.I)
DISTINCT_DIGITS = 3    # a figure of at least this many digits (61.27, 1244, 560.20) is rarely the same number by chance
ATTACH_SPAN = 28       # characters after a figure that can hold its own year label ("in H1 FY27", "for the financial year 2024-25")
BIND_WINDOW = 90 # characters between "over the last three years" and the figure it binds
BIND_AFTER, BIND_BEFORE = 30, 15      # "average ... of 12%" (the figure follows) and "12% on average" (it comes first)


def fiscal_years(text):
    """The years ending March that a text names, as ints: "FY 2025-26" -> {2026}; "FY 2026", "FY26" -> {2026}."""
    out = set()
    for m in RE_FY_RANGE.finditer(text):
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        end = int(b) if len(b) == 4 else int(a[:2] + b)
        if len(b) == 2 and end < int(a):
            end += 100
        if end - int(a) == 1:                      # "2025-26" is a fiscal year; "2020-31" is not
            out.add(end)
    for m in RE_FY_SINGLE.finditer(text):
        y = m.group(1)
        out.add(int(y) if len(y) == 4 else 2000 + int(y))
    return out


def cues(text):
    """{"fy": years, "half": bool, "multi": bool} for a clause or an evidence text."""
    return {"fy": fiscal_years(text), "half": bool(RE_HALF.search(text)), "multi": bool(RE_MULTI.search(text))}


def compatible(claim, ev):
    """May evidence with cues ev support a clause with cues claim? See the module docstring."""
    if claim["multi"] and not ev["multi"]:
        return False
    if (claim["fy"] or claim["half"]) and (ev["fy"] or ev["half"]) and claim["half"] != ev["half"]:
        return False                                   # a half-year or quarter figure for a full year, or the reverse
    if claim["fy"] and ev["fy"] and not (claim["fy"] & ev["fy"]):
        return False
    return True


RE_CLAIM = re.compile(r"(?<![\w.,/])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w/]|\.\d)")
RE_PCT = re.compile(r"\s*(?:%|per\s?cent\b)", re.I)
RE_MONEY_AFTER = re.compile(r"\s*(?:lakhs?|lacs?|crores?|cr\b|million|billion|mn\b|bn\b)", re.I)
RE_MONEY_BEFORE = re.compile(r"(?:₹|Rs\.?|INR|USD|US\$|\$)\s*$", re.I)
RE_DATE_BLANK = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}(?:\s*,?\s*\d{{4}})?|\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}"
                           rf"|\b{_MONTHS}\s+\d{{4}}", re.I)
RE_CLAUSE_SPLIT = re.compile(r"[;()\n]|,\s|(?<=[.!?])\s+")
RE_SENTENCES = re.compile(r"[^\n]+?(?:(?<=[.!?])\s+|\n+|$)")      # a "." inside "61.27" does not end a sentence
RE_ATTACHED = re.compile(r"^\s*(?:%|per\s?cent|lakhs?|lacs?|crores?|cr\b|million|billion|mn\b|bn\b)?\s*"
                         r"(?:\(\s*(?:for\s+)?|\b(?:for|in|during|of)\s+(?:the\s+)?(?:(?:financial|fiscal)\s+year\s+|year\s+)?)", re.I)


def _blank(text):
    """text with fiscal-year labels and dates blanked out (same length), so their digits are not read as figures."""
    for rx in (RE_FY_RANGE, RE_FY_SINGLE, RE_DATE_BLANK):
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


def is_quantity(text, m):
    """Is the number m a percentage or a money amount ("61%", "₹ 560.20 lakhs", "Rs. 5 crore")?"""
    return bool(RE_PCT.match(text, m.end(1)) or RE_MONEY_AFTER.match(text, m.end(1)) or RE_MONEY_BEFORE.search(text[:m.start(1)]))


def attached_years(sentence, end):
    """The fiscal year a figure is stated for when the sentence says so right after it ("₹710.04 lakh for FY 2024",
    "₹5,181.90 lakh (FY 2024)")."""
    after = sentence[end:end + 60]
    m = RE_ATTACHED.match(after)
    if not m:
        return set()
    return fiscal_years(after[m.end():m.end() + 14])


def near_years(text, k):
    """The fiscal year whose label stands nearest to the number k in text ("... 0.42% of dispatches (FY 2024-25: 0.57%)": the
    year of 0.57 is FY 2024-25, not both); every year named when the number cannot be located."""
    labels = [(m.start(), m.end(), fiscal_years(m.group(0))) for rx in (RE_FY_RANGE, RE_FY_SINGLE) for m in rx.finditer(text)]
    labels = [x for x in labels if x[2]]
    if not labels:
        return set()
    spots = [(m.start(1), m.end(1)) for m in RE_CLAIM.finditer(_blank(text)) if num_key(m.group(1)) == k]
    if not spots or len(labels) == 1:
        return set().union(*(x[2] for x in labels))
    gap = lambda a, b: 0 if not (a[1] <= b[0] or a[0] >= b[1]) else min(abs(a[0] - b[1]), abs(b[0] - a[1]))   # noqa: E731
    return min(((gap(label, spot), label[2]) for label in labels for spot in spots), key=lambda x: x[0])[1]


def pair_in_order(sent):
    """{start of the number: (years, half)} for a sentence that gives several figures and as many fiscal-year labels, each figure
    with its own: either it says "respectively" ("₹1,244 lakhs and ₹616 lakhs respectively" in "FY 2026-27 and FY 2027-28": the n-th
    figure is the n-th year's), or figures and labels strictly alternate ("₹616 lakhs in FY 2026-27 and ₹1,244 lakhs in FY 2027-28",
    "in FY 2025-26 12% and in FY 2024-25 9%"). {} otherwise."""
    blanked = _blank(sent)
    figures = [m for m in RE_CLAIM.finditer(blanked) if is_quantity(blanked, m) and not re.fullmatch(r"(?:19|20)\d{2}", m.group(1))]
    seen, labels = set(), []
    for rx in (RE_FY_RANGE, RE_FY_SINGLE):
        for m in rx.finditer(sent):
            ys = fiscal_years(m.group(0))
            if ys and m.start() not in seen:
                seen.add(m.start())
                labels.append((m.start(), m.end(), ys))
    labels.sort()
    if len(figures) < 2 or len(figures) != len(labels):
        return {}
    half = lambda l: bool(RE_HALF.search(sent[max(0, l[0] - 8):l[1]]))      # noqa: E731
    if re.search(r"\brespectively\b", sent, re.I):
        return {f.start(1): (l[2], half(l)) for f, l in zip(figures, labels)}
    seq = sorted([(f.start(1), "f", f) for f in figures] + [(l[0], "l", l) for l in labels], key=lambda x: x[0])
    if any(a[1] == b[1] for a, b in zip(seq, seq[1:])):
        return {}                                                         # not strictly alternating
    pairs = zip(seq[0::2], seq[1::2])
    out = {}
    for a, b in pairs:
        f, l = (a[2], b[2]) if a[1] == "f" else (b[2], a[2])
        out[f.start(1)] = (l[2], half(l))
    return out


def _fact_evidence(f):
    """[(num_key, text, cues)] one fact contributes (see _evidence)."""
    out = {}

    def add(k, text, years=None, half=None):
        if k is not None:
            k = abs(k)                                     # a claim reads "₹-0.42 lakhs" as 0.42: the sign is not part of it
            c = cues(text)
            c["fy"] = near_years(text, k) if years is None else years
            if half is not None:
                c["half"] = half
            out.setdefault(k, []).append((text, c))

    val = str(f.get("value", ""))
    if len(val) > 120 or f.get("type") == "text" or f.get("origin") == "passage":        # a passage: its sentences
        for m in RE_SENTENCES.finditer(val):
            sent = m.group(0)
            paired = pair_in_order(sent)
            for x in RE_ANYNUM.findall(_blank(sent)):
                add(num_key(x), sent)
            for pos, (ys, hf) in paired.items():                  # "respectively": each figure keeps its own year
                x = RE_CLAIM.match(_blank(sent), pos)
                if x:
                    out.setdefault(abs(num_key(x.group(1))), [])
                    out[abs(num_key(x.group(1)))] = [e for e in out[abs(num_key(x.group(1)))] if e[0] != sent]
                    add(num_key(x.group(1)), sent, ys, hf)
        return out
    text = " ".join(str(f.get(k) or "") for k in ("label", "snippet", "period"))
    own = fiscal_years(str(f.get("period") or ""))
    add(num_key(val), text, own or None)
    snippet = str(f.get("snippet") or "")
    for x in RE_ANYNUM.findall(_blank(snippet)):                          # a figure stated beside it in the same snippet:
        add(num_key(x), text, near_years(snippet, num_key(x)),            # its year is the snippet's, never this fact's typed one;
            bool(RE_HALF.search(snippet)))                                # nor does it inherit this fact's "H1" period
    return out


# A draft is guarded paragraph by paragraph, each time against the same few thousand facts; reading every fact again each time took
# 7 s of 9 s per paragraph at 7,700 facts (22 Nov 2026, Vidyunmaya data room: a section took minutes on the pod). What one fact
# contributes depends only on the fact, so it is read once and kept, keyed by the fact object and checked against its content.
_FACT_CACHE = {}
FACT_CACHE_MAX = 60000


def _fact_key(f):
    return (f.get("value"), f.get("snippet"), f.get("label"), f.get("period"), f.get("type"), f.get("origin"))


def _evidence(facts):
    """{num_key: [(text, cues)]}: for each number, the texts that state it (kept per facts list, verify/memo.py; read only)."""
    from verify.memo import memo
    return memo(facts, "evidence", lambda: _build_evidence(facts))


def _build_evidence(facts):
    """A typed fact is its label, snippet and period (the typed period is the figure's year when it has one, else the year label
    nearest the figure); a passage contributes the sentence that holds the number."""
    out = {}
    if len(_FACT_CACHE) > FACT_CACHE_MAX:
        _FACT_CACHE.clear()
    for f in facts:
        if f.get("superseded"):
            continue
        hit = _FACT_CACHE.get(id(f))
        key = _fact_key(f)
        if hit is None or hit[0] is not f or hit[1] != key:
            hit = _FACT_CACHE[id(f)] = (f, key, _fact_evidence(f))
        for k, ents in hit[2].items():
            out.setdefault(k, []).extend(ents)
    return out


def cu_for(pieces, raw):
    """the evidence pieces that count for a figure: a distinctive one ignores sources that say nothing about a period."""
    cu = [e for _, e in pieces]
    if len(re.sub(r"\D", "", raw)) >= DISTINCT_DIGITS:
        cu = [e for e in cu if e["fy"] or e["half"] or e["multi"]] or cu
    return cu


def mask_period_claims(text, facts):
    """text with each percentage or money amount replaced by [●] whose period or basis contradicts all the evidence for it;
    returns (text, masked) like mask_ungrounded, kind "period_basis"."""
    ev = _evidence(facts)
    hits = []
    for sm in RE_SENTENCES.finditer(text):
        sent, s0 = sm.group(0), sm.start()
        # basis cues are read over the whole sentence ("On average, complaints were 0.42%": a comma separates them) but bind
        # only by distance; fiscal-year cues are read per clause
        cue_spans = [(m.span(), bool(RE_AVG.fullmatch(m.group(0)))) for m in RE_MULTI.finditer(sent)]
        sent_years = fiscal_years(sent)
        paired = pair_in_order(sent)
        start, carry, carry_half = 0, set(), False   # carry: the year (and half-year cue) a number-free lead-in names ("In H1 FY27, ...")
        for end in [m.end() for m in RE_CLAUSE_SPLIT.finditer(sent)] + [len(sent)]:
            clause, c0 = sent[start:end], start
            start = end
            own = cues(clause)
            blanked = _blank(clause)
            label_only = bool(own["fy"]) and not RE_CLAIM.search(blanked)
            if label_only and sent[c0 - 1:c0] == "(":
                continue                                       # "(FY 2024)" after a figure labels that figure; it leads nothing
            years = own["fy"] or carry
            lead_half = own["half"] or (carry_half and not own["fy"])
            carry_half = own["half"] if label_only else (False if own["fy"] else carry_half)
            carry = own["fy"] if label_only else (set() if own["fy"] else carry)
            if label_only:
                continue
            for m in RE_CLAIM.finditer(blanked):
                raw = m.group(1)
                k = num_key(raw)
                if k is None or re.fullmatch(r"(?:19|20)\d{2}", raw) or not is_quantity(blanked, m):
                    continue
                pieces = ev.get(k)
                if not pieces:
                    continue                                   # nothing states it: mask_ungrounded's case
                own_fy = attached_years(sent, c0 + m.end(1))
                p = c0 + m.start(1)
                if p in paired:                                # "... in FY 2023-24, FY 2024-25 and H1 FY 2027 respectively"
                    ys, hf = paired[p]
                    if any(compatible({"fy": ys, "half": hf, "multi": False}, e) for e in cu_for(pieces, raw)):
                        continue
                    a = s0 + p
                    hits.append({"kind": "period_basis", "raw": raw, "start": a, "end": a + len(raw),
                                 "context": text[max(0, a - 60):a + len(raw) + 40]})
                    continue
                # a clause that names its own year is bound only by a cue in the same clause
                spans = [x for x in cue_spans if c0 <= x[0][0] < c0 + len(clause)] if own["fy"] else cue_spans
                near = any((a - BIND_BEFORE <= p <= b + BIND_AFTER) if avg else (a - BIND_WINDOW <= p <= b + BIND_WINDOW)
                           for (a, b), avg in spans)
                half = lead_half
                if own_fy:
                    # "₹149.74 in FY 2023-24 ... and ₹175.5 in the six months ended": the half-year cue belongs to the figure it
                    # follows, not to every figure of the clause; a figure with its own year label is half-year only if the
                    # words around that label say so ("in H1 FY27")
                    half = bool(RE_HALF.search(sent[c0 + m.end(1):c0 + m.end(1) + 60][:ATTACH_SPAN]))
                other = set()
                for m2 in RE_CLAIM.finditer(blanked):
                    if m2.start(1) != m.start(1):
                        other |= attached_years(sent, c0 + m2.end(1))
                c = {"fy": own_fy or (years - other) or (set() if other and half else years), "half": half,
                     "multi": near and not own_fy and len(sent_years) <= 1}
                if not (c["fy"] or c["half"] or c["multi"]):
                    continue
                cu = [e for _, e in pieces]
                if len(re.sub(r"\D", "", raw)) >= DISTINCT_DIGITS:
                    # a distinctive figure that some source states for a period is that period's figure: a source that says
                    # nothing about the period (a total, a table row) cannot lend it to another one
                    cu = [e for e in cu if e["fy"] or e["half"] or e["multi"]] or cu
                if any(compatible(c, e) for e in cu):
                    continue
                a = s0 + c0 + m.start(1)
                hits.append({"kind": "period_basis", "raw": raw, "start": a, "end": a + len(raw),
                             "context": text[max(0, a - 60):a + len(raw) + 40]})
    for h in reversed(hits):
        text = text[:h.pop("start")] + PH + text[h.pop("end"):]
    return text, hits



# --- a year after the document's own date, said to have begun ------------------------------------------------------------
# Hosted test of 22 Nov 2026: "FSSC 22000 v6 certified since 2027". The source lists the certificate's EXPIRY (2 November 2027)
# in a licence table; the draft read it as a start. A document dated after September 2026 cannot say that anything has
# existed "since 2027", whatever its sources hold. Only the unambiguous case is masked: a calendar year later than the latest
# date the inputs call a reporting date ("ended", "as at", "as of"), after "since" or after a verb of beginning.
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
RE_ASOF = re.compile(r"\b(?:ended|as\s+at|as\s+of)\s+(?:the\s+)?(?:\d{1,2}(?:st|nd|rd|th)?\s+)?" + _MONTH + r",?\s+(20\d\d)\b", re.I)
RE_BEGAN = re.compile(
    r"\b(?:since|(?:incorporated|established|founded|set\s+up|commissioned|commenced(?:\s+operations)?|started(?:\s+operations)?|"
    r"certified|registered|operating|in\s+operation)\s+(?:in|since))\s+(?:the\s+year\s+)?(?<![\w-])(20\d\d)(?![\d/-])", re.I)


def reporting_year(facts):
    """the latest calendar year the inputs give as a reporting date ("six months ended 30 September 2026"), else None."""
    from verify.memo import memo

    def build():
        years = []
        for f in facts:
            if f.get("superseded"):
                continue
            blob = " ".join(str(f.get(k) or "") for k in ("label", "snippet", "period", "value"))
            years += [int(y) for y in RE_ASOF.findall(blob)]
        return max(years) if years else None
    return memo(facts, "reporting_year", build)


def mask_future_dates(text, facts):
    """text with a year that lies after the reporting date, said to have begun ("certified since 2027"), replaced by [●];
    returns (text, masked), kind "future_date". Does nothing when the inputs name no reporting date."""
    asof = reporting_year(facts)
    if asof is None:
        return text, []
    hits = []
    for m in RE_BEGAN.finditer(text):
        if int(m.group(1)) > asof:
            hits.append({"kind": "future_date", "raw": m.group(1), "start": m.start(1), "end": m.end(1),
                         "context": text[max(0, m.start(1) - 60):m.end(1) + 40]})
    for h in reversed(hits):
        text = text[:h.pop("start")] + PH + text[h.pop("end"):]
    return text, hits


# --- a month and year taken from another event of the same list ----------------------------------------------------------
# Hosted test of 22 Nov 2026, twice: "FSSC 22000 certification since June 2025". The timeline row reads "2025 | FSSC 22000
# certification; revenue crossed ₹100 crore; activated-carbon VOC control unit installed (June 2025)": the month belongs to the last
# item. The date is in the inputs, so mask_ungrounded keeps it. A month-year (no day) is kept only if some source places it beside
# at least one content word of the words that lead into it; the source's items are cut at ";", "|" and line ends, so a date in
# brackets stays with the item it closes. Not checked: a date that no source states (mask_ungrounded), and dates with a day.
RE_MONTHYEAR = re.compile(rf"(?<![\w])(?<!\d )(?<!\d\w\w )({_MONTHS})\s+(20\d\d)\b", re.I)
RE_ANYMONTHYEAR = re.compile(rf"\b({_MONTHS})\s+(20\d\d)\b", re.I)
RE_ITEM_SPLIT = re.compile(r"[;|\n]")
_LEAD_SPLIT = re.compile(r"[;|\n()]|,\s|(?<=[.!?])\s+")
_STOP = {"since", "with", "from", "that", "this", "which", "were", "been", "have", "also", "during", "upon", "into", "than",
         "then", "company", "limited", "date", "year", "years", "month", "months", "after", "before", "until", "when", "while",
         "their", "there", "these", "those", "being", "work", "ended", "held", "term", "the", "and", "for", "was", "are", "its"}


def _stems(text):
    return {w[:4] for w in re.findall(r"[A-Za-z0-9]{3,}", RE_ANYMONTHYEAR.sub(" ", text).lower()) if w not in _STOP and not
            re.fullmatch(r"20\d\d", w)}


def mask_event_dates(text, facts):
    """text with each month-year ("June 2025") replaced by [●] when every source that holds it holds it beside none of the words
    leading into it in the draft; returns (text, masked), kind "event_date"."""
    from verify.memo import memo

    def build():
        holders = {}

        def add(key, item, label=""):
            holders.setdefault(key, []).append(_stems(label + " " + item))
        for f in facts:
            if f.get("superseded"):
                continue
            label = str(f.get("label") or "")
            for field in ("snippet", "value"):
                blob = str(f.get(field) or "")
                for item in RE_ITEM_SPLIT.split(blob):
                    for m in RE_ANYMONTHYEAR.finditer(item):
                        add((m.group(1).lower()[:3], m.group(2)), item, label if field == "value" else "")
        return holders
    holders = memo(facts, "event_holders", build)
    hits = []
    for m in RE_MONTHYEAR.finditer(text):
        key = (m.group(1).lower()[:3], m.group(2))
        pieces = holders.get(key)
        if not pieces:
            continue                                       # no source states it: mask_ungrounded's case
        start = max((x.end() for x in _LEAD_SPLIT.finditer(text, 0, m.start())), default=0)
        lead = _stems(text[max(start, m.start() - 80):m.start()])
        if not lead or any(lead & p for p in pieces):
            continue
        hits.append({"kind": "event_date", "raw": m.group(0), "start": m.start(), "end": m.end(),
                     "context": text[max(0, m.start() - 60):m.end() + 40]})
    for h in reversed(hits):
        text = text[:h.pop("start")] + PH + text[h.pop("end"):]
    return text, hits


# --- malformed amounts ---------------------------------------------------------------------------------------------------
# Hosted test of 22 Nov 2026, third redraft: "borrow up to ₹75,0,0,0,00" (for ₹75,00,00,000) and "revised from ₹4800 MT to ₹3984 MT".
# Both values are in the inputs once their text is cleaned up, so the value check keeps them. Two shapes that no source writes:
#   * a number after a rupee sign whose comma groups are neither Western (1,234,567) nor Indian (12,34,567);
#   * a rupee sign in front of a quantity of something else ("₹4800 MT", "₹229 million pieces", "₹312 employees").
# The number is masked; the words around it stay.
_RUPEE = r"(?<![A-Za-z])(?:₹|Rs\.?|INR)\s*"
RE_AMOUNT_CHAIN = re.compile(rf"({_RUPEE})(\d[\d,]*\d)(?![\d,])")
RE_GROUPING = re.compile(r"\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3}")
RE_RUPEE_QUANTITY = re.compile(
    rf"({_RUPEE})(\d[\d,]*(?:\.\d+)?)(?=\s*(?:MTPA|MT|tonnes?|tons?|kgs?|sq\.?\s?(?:m|ft|mtrs?)|million\s+(?:pieces|pcs|units)|"
    r"pieces|pcs|employees|workers|persons|years|%)\b)", re.I)


def mask_malformed_amounts(text, facts=()):
    """text with each rupee amount whose comma groups are malformed, or that stands before a unit that is not money, replaced by
    [●] (the number only); returns (text, masked), kind "malformed_amount". A form the inputs themselves write (a typo in the
    source) is the source's, and is left to the reviewer."""
    from verify.memo import memo
    blob = memo(facts, "amount_blob", lambda: " ".join(str(f.get(k) or "") for f in facts for k in ("snippet", "value")))
    hits = []
    for m in RE_AMOUNT_CHAIN.finditer(text):
        raw = m.group(2)
        if "," in raw and not RE_GROUPING.fullmatch(raw) and m.group(0) not in blob:
            hits.append((m.start(2), m.end(2), raw))
    for m in RE_RUPEE_QUANTITY.finditer(text):
        if not any(a <= m.start(2) < b for a, b, _ in hits) and m.group(0) not in blob:
            hits.append((m.start(2), m.end(2), m.group(2)))
    out = []
    for a, b, raw in sorted(hits, reverse=True):
        out.append({"kind": "malformed_amount", "raw": raw, "context": text[max(0, a - 60):b + 40]})
        text = text[:a] + PH + text[b:]
    return text, out[::-1]


# --- the unit of a rupee amount -----------------------------------------------------------------------------------------------
# 22 Nov 2026, second hosted test (Rasoiyana): a table headed "(₹ lakhs; %)" holds "4,012.19 (43.2)", and the draft said "₹4,012.19
# million (43.2% of sales)": a hundredfold misstatement with the right digits, so the value check keeps it. The unit of an amount in the
# draft must be one the inputs give for that number: where some source writes the number next to a unit, the draft's unit must be among
# them; where the number sits in a table cell (its unit is in the header), the draft's unit must not be one the inputs hardly use for
# rupee amounts (fewer than a tenth of the uses of the commonest). A number no source holds is left to the value check.
_UNIT = r"(million|mn|crores?|cr|lakhs?)"
RE_UNIT_CLAIM = re.compile(rf"(?:₹|Rs\.?)\s?(\d[\d,]*(?:\.\d+)?)\s*{_UNIT}\b", re.I)
RE_UNIT_SEEN = re.compile(rf"(?<![\d.,])(\d[\d,]*(?:\.\d+)?)\s*\)?\s*{_UNIT}\b", re.I)


def _unit_norm(u):
    u = u.lower()
    return "million" if u in ("million", "mn") else "crore" if u.startswith("cr") else "lakh"


def _unit_tables(facts):
    from verify.memo import memo

    def build():
        seen, count, allnums = {}, {}, set()
        for f in facts:
            if f.get("superseded"):
                continue
            blob = " ".join(str(f.get(k) or "") for k in ("label", "value", "snippet", "unit"))
            for m in RE_UNIT_SEEN.finditer(blob):
                k, u = num_key(m.group(1)), _unit_norm(m.group(2))
                if k is not None:
                    seen.setdefault(k, set()).add(u)
            for m in re.finditer(rf"(?:₹|Rs\.?)\s?\d[\d,]*(?:\.\d+)?\s*{_UNIT}\b", blob, re.I):
                u = _unit_norm(m.group(1))
                count[u] = count.get(u, 0) + 1
            for x in RE_ANYNUM.findall(blob):
                k = num_key(x)
                if k is not None:
                    allnums.add(abs(k))
        return seen, count, allnums
    return memo(facts, "unit_tables", build)


def mask_unit_claims(text, facts):
    """text with each rupee amount whose unit (lakhs, crore, million) the inputs do not give for it replaced by [●] (the number only);
    returns (text, masked), kind "unit_mismatch"."""
    seen, count, allnums = _unit_tables(facts)
    top = max(count.values()) if count else 0
    hits = []
    for m in RE_UNIT_CLAIM.finditer(text):
        k, u = num_key(m.group(1)), _unit_norm(m.group(2))
        if k is None:
            continue
        have = seen.get(k) or seen.get(abs(k))
        if have:
            bad = u not in have
        else:
            bad = abs(k) in allnums and top >= 10 and count.get(u, 0) * 10 < top
        if bad:
            hits.append({"kind": "unit_mismatch", "raw": m.group(1), "start": m.start(1), "end": m.end(1),
                         "context": text[max(0, m.start() - 60):m.end() + 40]})
    for h in reversed(hits):
        text = text[:h.pop("start")] + PH + text[h.pop("end"):]
    return text, hits
