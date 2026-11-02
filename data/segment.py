"""Segmenter (PLAN.md 5.1): split a section into the sub-sections under its real headings.

    segment(section, vocab) -> [Unit]

Headings are short lines in capitals or title case that do not end a sentence. Risk factors are split at
their numbers ("12. We depend on ..."), and up to four short ones are grouped. Units are 150-1,500 tokens:
longer ones are split at paragraph boundaries (marked continuation), shorter ones merged with the next.
Every unit keeps the section outline (its sibling headings) and the text of the unit before it, from which
the previous-unit summary is built.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .clean import clean_lines, reflow, table_like
from .corpus import Section

MIN_TOK, MAX_TOK, SPLIT_TOK = 150, 1500, 1000
RE_RF = re.compile(r"^\s*(\d{1,3})\s?[.)]\s+(?=[A-Z“\"'])")
SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "our", "its", "vs", "&"}


def tokens(text):
    """Qwen tokens, approximated: offer-document English averages about 1.3 tokens per word."""
    return int(len(text.split()) * 1.3) + 1


def is_heading(line, prev_blank):
    s = line.strip().strip("*:").strip()
    if not (3 <= len(s) <= 90) or s.endswith((".", ",", ";")) or len(s.split()) > 12:
        return False
    if re.match(r"^[\d\W]+$", s) or re.search(r"\d{3,}", s) or s.count("|") or re.match(r"^(note|source|\*)", s, re.I):
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 3:
        return False
    if ":" in s.rstrip(":"):
        return False                      # "Designation: Managing Director" is a form line, not a heading
    low = [w.lower() for w in re.findall(r"[A-Za-z]+", s)]
    if len(low) >= 3 and len(set(low)) <= len(low) - 2:
        return False                      # "Particulars Actual Actual Actual" is a table header
    if re.search(r"\b(particulars|s\.\s?no|sr\.\s?no|amt\.?|amount|in lakhs?|in crores?)\b|\((?:₹|rs)", s, re.I):
        return False                      # table column headers
    if len(low) < 2 and not s.isupper():
        return False                      # a lone title-case word ("Arnav") is a name in a table, not a heading
    upper = sum(c.isupper() for c in letters) / len(letters)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’&-]*", s)]
    title = words and sum(w[0].isupper() or w.lower() in SMALL for w in words) / len(words) >= 0.85 and words[0][0].isupper()
    numbered = bool(re.match(r"^(\(?[A-Za-z0-9ivx]{1,4}[.)])\s+[A-Z]", s))
    return upper >= 0.8 or (title and (prev_blank or numbered) and len(words) >= 1)


@dataclass
class Unit:
    unit_id: str
    split: str
    doc_id: int
    company: str
    listing_year: int
    section_key: str
    outline_key: str
    section_title: str
    heading: str
    index: int
    raw: str                      # cleaned unit text (pre-mask), the teacher's source
    n_tokens: int
    continuation: bool = False
    merged_headings: list = field(default_factory=list)
    outline: list = field(default_factory=list)
    prev_text: str = ""
    page_start: int = 0

    def to_dict(self):
        return asdict(self)


def _blocks(section: Section, vocab):
    """(heading, text) blocks in document order."""
    lines = clean_lines(section.text, vocab)
    if lines and lines[0].strip().upper().endswith(section.title.strip().upper()[-20:]):
        lines = lines[1:]                                 # the section title itself
    blocks, head, buf, prev_blank = [], "Introduction", [], True
    rf = section.section_key == "risk_factors"
    for ln in lines:
        s = ln.strip()
        if not s:
            buf.append("")
            prev_blank = True
            continue
        m = RE_RF.match(s) if rf else None
        if m:
            if any(x.strip() for x in buf):
                blocks.append((head, "\n".join(buf)))
            first = re.split(r"(?<=[.?!])\s", s[m.end():], maxsplit=1)[0]
            head, buf = f"{m.group(1)}. {first[:140]}", [s]
        elif is_heading(s, prev_blank) and not rf or (rf and is_heading(s, prev_blank) and s.isupper()):
            if any(x.strip() for x in buf):
                blocks.append((head, "\n".join(buf)))
            head, buf = s.strip("*: "), []
        else:
            buf.append(s)
        prev_blank = False
    if any(x.strip() for x in buf):
        blocks.append((head, "\n".join(buf)))
    return blocks


def _split_long(head, text):
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], []
    for p in paras:
        cur.append(p)
        if tokens("\n\n".join(cur)) >= SPLIT_TOK:
            out.append("\n\n".join(cur))
            cur = []
    if cur:
        if out and tokens("\n\n".join(cur)) < MIN_TOK:
            out[-1] += "\n\n" + "\n\n".join(cur)
        else:
            out.append("\n\n".join(cur))
    return [(head, t, i > 0) for i, t in enumerate(out)]


def segment(section: Section, vocab) -> list[Unit]:
    blocks = _blocks(section, vocab)
    rf = section.section_key == "risk_factors"
    merged = []                                    # (heading, text, continuation, merged headings)
    pend = None
    for head, text in blocks:
        if pend is None:
            pend = [head, text, [head]]
        else:
            limit = 4 if rf else 99
            if tokens(pend[1]) < MIN_TOK and len(pend[2]) < limit:
                pend[1] += "\n\n" + (text if rf else f"{head}\n{text}")
                pend[2].append(head)
            else:
                merged.append(pend)
                pend = [head, text, [head]]
    if pend:
        merged.append(pend)
    units, outline = [], []
    pieces = []
    for head, text, heads in merged:
        if tokens(text) > MAX_TOK:
            pieces += [(h, t, c, heads) for h, t, c in _split_long(head, text)]
        else:
            pieces.append((head, text, False, heads))
    outline = list(dict.fromkeys(h for h, _t, c, _hs in pieces if not c))
    prev = ""
    for i, (head, text, cont, heads) in enumerate(pieces):
        body = reflow(text)
        u = Unit(f"{section.split[:2]}-{section.doc_id}-{section.outline_key}-{i:03d}", section.split, section.doc_id,
                 section.company, section.listing_year, section.section_key, section.outline_key, section.title,
                 head, i, body, tokens(body), cont, heads[1:], outline, prev, section.page_start)
        prev = body
        if MIN_TOK <= u.n_tokens <= MAX_TOK * 1.2 and not table_like(text):
            units.append(u)
    return units
