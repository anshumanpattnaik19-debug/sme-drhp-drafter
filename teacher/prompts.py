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
