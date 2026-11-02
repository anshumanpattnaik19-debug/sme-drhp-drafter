"""Prompt formats shared by training and inference. The app's writer imports these, so the student sees the
same input at inference as in training (PLAN.md section 4, step 5).

    drafting_messages(company, section_title, outline, heading, facts, prev_summary, precedent=None)
    extraction_messages(text, section_title=None)
    summary_of(text)   the previous-unit summary: the first two sentences, at most 60 words
    trim_repeats(text) cuts a generated draft where it starts looping
"""
from __future__ import annotations

import json
import re

DRAFT_SYSTEM = (
    "You draft one sub-section of an SME Draft Red Herring Prospectus (SEBI ICDR Regulations, Chapter IX) for review by "
    "the lead manager and legal counsel. Use only the FACTS given; some facts belong to other sub-sections, so use only "
    "those relevant to this sub-heading. Every figure, date and name you write must appear in FACTS. Where the "
    "sub-section needs a detail that FACTS do not give, write [●] and do not guess. Offer price, price band, issue size "
    "in rupees and offer dates are [●] at DRHP stage. Write in the formal third person of offer documents ('our "
    "Company'). Write only the body of the sub-section, without its heading.")

EXTRACT_SYSTEM = (
    "You extract typed facts from a passage of an Indian SME offer document or issuer file. Return JSON only: "
    '{"facts": [{"type": "amount|percent|date|count|person|entity|place|short_text", "label": "...", "value": "...", '
    '"unit": "...", "period": "..."}]}. Copy each value exactly as written. Include every figure, date and proper name '
    "in the passage. short_text values are at most 12 words and must not copy a sentence. Ignore page references.")

MAX_FACTS = 60
PRECEDENT_WORDS = 1400


def summary_of(text, words=60):
    sents = re.split(r"(?<=[.?!])\s+", " ".join(text.split()))
    s = " ".join(sents[:2])
    w = s.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def _fact_lines(facts):
    rows = [{k: f[k] for k in ("type", "label", "value", "unit", "period") if f.get(k)} for f in facts[:MAX_FACTS]]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def drafting_messages(company, section_title, outline, heading, facts, prev_summary="", precedent=None):
    parts = [f"COMPANY: {company}", f"SECTION: {section_title}",
             "SECTION OUTLINE: " + " | ".join(h for h in outline[:30]),
             f"SUB-HEADING: {heading}",
             f"PREVIOUS SUB-SECTION (summary): {prev_summary or '(start of section)'}",
             f"FACTS: {_fact_lines(facts)}"]
    if precedent:
        words = precedent.split()
        parts.append("PRECEDENT (same sub-heading in another company's offer document; for structure and tone only, "
                     "never for figures or names):\n" + " ".join(words[:PRECEDENT_WORDS]))
    parts.append("Draft the sub-section now.")
    return [{"role": "system", "content": DRAFT_SYSTEM}, {"role": "user", "content": "\n".join(parts)}]


RE_SENT_END = re.compile(r".+?(?:(?<=[.;:])\s+|\n+|$)", re.S)


def trim_repeats(text, min_chars=25, max_seen=2):
    """Cut a draft where greedy decoding starts looping: a sentence seen a third time cuts the text back to just
    before its second occurrence. Real offer-document text repeats a sentence once ("The details of his remuneration
    are as set out below:"), a loop repeats it many times. Numbers are ignored when comparing, so "36. Welding
    Machine 2 Unit" repeats "35. Welding Machine 2 Unit". Returns (text, was_cut)."""
    where, out = {}, []
    for m in RE_SENT_END.finditer(text):
        s = m.group(0).strip()
        if not s:
            continue
        key = re.sub(r"\d+", "#", s)
        if len(s) > min_chars:
            where.setdefault(key, []).append(len(out))
            if len(where[key]) > max_seen:
                return "".join(out[:where[key][1]]).strip(), True
        out.append(m.group(0))
    return text.strip(), False


def extraction_messages(text, section_title=None):
    head = f"SECTION: {section_title}\n" if section_title else ""
    return [{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": f"{head}PASSAGE:\n{text}"}]
