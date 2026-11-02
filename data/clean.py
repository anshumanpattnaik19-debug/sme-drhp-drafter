"""Target cleaning (PLAN.md 5.3): page headers and footers out, PDF-broken words rejoined, flattened tables found.

    vocab = build_vocab(texts)
    lines = clean_lines(text, vocab)          # before segmentation (headings still on their own lines)
    reflow(text) -> paragraphs                 # after segmentation, for the training target
    table_like(text) -> bool                   # units that are mostly a flattened table are skipped
    strip_tables(text) -> (text, n_tables)     # flattened tables inside a drafting target are cut out
"""
from __future__ import annotations

import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]+")
RE_PAGE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.I)
RE_SPLIT_YEAR = re.compile(r"\b((?:19|20)\d{1,2})\s(\d{1,2})\b")


def build_vocab(texts):
    c = Counter()
    for t in texts:
        c.update(w.lower() for w in WORD.findall(t))
    return c


def _rejoin(line, vocab):
    """'inclu ding' -> 'including', 'Sh ares' -> 'Shares' when the joined word is common and a part is rare."""
    toks = line.split(" ")
    out, i = [], 0
    while i < len(toks):
        a = toks[i]
        if i + 1 < len(toks):
            b = toks[i + 1]
            if a.isalpha() and b and WORD.fullmatch(b.rstrip(".,;:)")):
                core_b = b.rstrip(".,;:)")
                joined = (a + core_b).lower()
                fj, fa, fb = vocab.get(joined, 0), vocab.get(a.lower(), 0), vocab.get(core_b.lower(), 0)
                if fj >= 5 and (min(fa, fb) * 20 < fj or min(len(a), len(core_b)) <= 2 and fj > max(fa, fb)):
                    out.append(a + b)
                    i += 2
                    continue
        out.append(a)
        i += 1
    s = " ".join(out)
    s = RE_SPLIT_YEAR.sub(lambda m: m.group(1) + m.group(2) if len(m.group(1) + m.group(2)) == 4 else m.group(0), s)
    return s


def clean_lines(text, vocab, repeat_min=3):
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    short = Counter(ln.strip() for ln in lines if 0 < len(ln.strip()) <= 80)
    out = []
    for ln in lines:
        s = re.sub(r"[ \t]+", " ", ln).strip()
        if not s:
            out.append("")
            continue
        if RE_PAGE.match(s) or (short[s] >= repeat_min and len(s.split()) <= 10 and not s.endswith(".")):
            continue                      # page numbers and running headers/footers
        out.append(_rejoin(s, vocab))
    return out


def reflow(text):
    """Join PDF line wraps inside paragraphs; keep blank-line paragraph breaks and list items."""
    paras, cur = [], []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if cur and (re.match(r"^(\(?[a-z0-9ivx]{1,4}[.)]|[•\-–])\s", s) or cur[-1].endswith((":",))):
            paras.append(" ".join(cur))
            cur = []
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(re.sub(r"\s+", " ", p).strip() for p in paras if p.strip())


def table_like(text):
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return True
    def row(ln):   # a table row: several numbers and few words around them (prose lines with figures are not rows)
        n = len(re.findall(r"\d[\d,]*\.?\d*", ln))
        return n >= 3 and len(re.findall(r"[A-Za-z]{2,}", ln)) <= 2 * n
    numeric = sum(1 for ln in lines if row(ln))
    toks = text.split()
    num_toks = sum(1 for t in toks if re.match(r"^[(\-]?[\d,]+\.?\d*%?[)]?$", t))
    return numeric / len(lines) > 0.5 or (toks and num_toks / len(toks) > 0.35)


RE_NUM_TOK = re.compile(r"^[(\-–]?[₹$]?\d[\d,]*\.?\d*%?\)?[,;]?$")
RE_YEAR_TOK = re.compile(r"^\(?(?:19|20)\d{2}\)?[,;.]?$")


def strip_tables(text, min_run=3, max_gap=6, label_back=8):
    """Cut flattened tables out of a drafting target. A table row flattens to a label and a run of `min_run` or more
    consecutive numbers ("Govt Dues 6.14 22.24 54.23"); rows whose runs are at most `max_gap` words apart are one table,
    and the first row's label (up to `label_back` words, not past a sentence end) goes with it. Prose with figures
    ("from 3.6% in 2025 to 1.9% in 2026") has no such runs and stays. The app builds ICDR tables from the issuer's
    schedules in code, so the model is not trained to write them."""
    paras, n = [], 0
    for para in text.split("\n\n"):
        toks = para.split()
        num = [bool(RE_NUM_TOK.match(t)) and not RE_YEAR_TOK.match(t) for t in toks]
        runs, i = [], 0
        while i < len(toks):
            j = i
            while j < len(toks) and num[j]:
                j += 1
            if j - i >= min_run:
                runs.append([i, j])
            i = max(j, i + 1)
        if not runs:
            paras.append(para)
            continue
        spans = [runs[0]]
        for a, b in runs[1:]:
            if a - spans[-1][1] <= max_gap:
                spans[-1] = [spans[-1][0], b]
            else:
                spans.append([a, b])
        keep = [True] * len(toks)
        for a, b in spans:
            s = a
            while s > 0 and a - s < label_back and not toks[s - 1].endswith((".", ":", ";")):
                s -= 1
            keep[s:b] = [False] * (b - s)
            n += 1
        rest = " ".join(t for t, k in zip(toks, keep) if k)
        if rest.strip():
            paras.append(rest)
    return "\n\n".join(paras), n
