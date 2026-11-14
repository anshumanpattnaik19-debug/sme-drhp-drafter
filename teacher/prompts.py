"""The teacher's fact-extraction prompt (one call per unit, PLAN.md 5.2)."""
from __future__ import annotations

TEACHER_SYSTEM = """You extract the facts a sub-section of an Indian SME offer document was written from.
Return JSON only, no prose and no code fences:
{"facts": [{"type": "...", "label": "...", "value": "...", "unit": "...", "period": "..."}]}

type is one of: amount, percent, date, count, person, entity, place, short_text.
Rules:
1. Include EVERY figure (amounts, percentages, counts, share numbers, ratios), EVERY date and EVERY proper name of a
   person, company, bank, authority, place or product in the passage. Missing one makes the example unusable.
2. Copy each value exactly as written in the passage (same digits, commas, decimals; "₹ 1,250.00 lakhs" stays as is).
3. label says what the value is, in 2-8 plain words, e.g. "Revenue from operations", "Shares held by promoter".
4. unit: "₹ lakhs", "₹ crore", "%", "equity shares", "MT" etc. when the passage gives one. period: "FY 2025-26",
   "as at 30 September 2026" etc. when the value belongs to a period.
5. short_text is for a non-numeric attribute (a designation, a product, a type of proceeding), at most 12 words,
   in your own words: never copy a sentence or a run of 8 or more words from the passage.
6. Ignore page numbers, cross-references ("see page 45"), section numbers and regulation numbers.
7. One fact per value. Do not add facts that are not in the passage."""


QA_TEACHER_SYSTEM = """You write question-answer pairs for training an assistant that helps a merchant banker prepare an
Indian SME Draft Red Herring Prospectus. Each pair is answered from ONE passage of a company's offer document.
Return JSON only, no prose and no code fences:
{"qa": [{"question": "...", "answer": "...", "quote": "...", "topic": "...", "source_doc": "..."}]}

Write exactly 2 pairs. Rules:
1. question: what a banker, analyst or lawyer preparing the DRHP would ask about this company, 6-30 words, answerable
   only from this passage (not general knowledge, not yes/no, not about page numbers or section numbers).
2. answer: 1-3 sentences in the formal style of an offer document, answering the question fully. Copy every figure,
   date and name exactly as the passage writes it. Add nothing the passage does not say.
3. quote: the shortest exact span of the passage (copied character for character, at most 300 characters) that
   contains everything the answer states.
4. topic: the thing asked about, as a noun phrase, e.g. "the revenue from operations for FY 2024-25".
5. source_doc: the issuer document a banker would ask for to verify the answer, e.g. "restated financial
   statements", "board resolution", "certificate from the statutory auditor", "lease deed", "litigation certificate".
6. The two pairs must ask about different facts."""


def qa_teacher_messages(unit, max_chars=3000):
    return [{"role": "system", "content": QA_TEACHER_SYSTEM},
            {"role": "user", "content": f"COMPANY: {unit['company']}\nSECTION: {unit['section_title']}\n"
                                        f"SUB-HEADING: {unit['heading']}\n\nPASSAGE:\n{unit['raw'][:max_chars]}"}]


def teacher_messages(unit):
    return [{"role": "system", "content": TEACHER_SYSTEM},
            {"role": "user", "content": f"SECTION: {unit['section_title']}\nSUB-HEADING: {unit['heading']}\n\nPASSAGE:\n{unit['raw']}"}]


GAPFILL_RULE = """
8. This is a second pass. The user lists items an earlier pass missed. Return a fact for each listed item that occurs
   in the passage, and nothing else: no facts for items that are not listed."""


def gapfill_messages(unit, missed):
    """Second-pass prompt: the passage plus the figures, dates and names the first pass did not turn into facts."""
    lines = [f"- figure: {x}" for x in missed.get("figures", [])] + [f"- date: {x}" for x in missed.get("dates", [])] + \
            [f"- name: {x}" for x in missed.get("names", [])]
    return [{"role": "system", "content": TEACHER_SYSTEM + GAPFILL_RULE},
            {"role": "user", "content": f"SECTION: {unit['section_title']}\nSUB-HEADING: {unit['heading']}\n\nPASSAGE:\n{unit['raw']}"
                                        "\n\nMISSED ITEMS (as written in the passage):\n" + "\n".join(lines)}]
