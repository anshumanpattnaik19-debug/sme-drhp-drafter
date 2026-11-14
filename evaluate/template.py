"""Baseline B2, the template (PLAN.md section 7.1): is fine-tuning worth it over boilerplate?

For each test drafting row: the train sub-section of the same section bucket whose heading is closest (word Jaccard,
list numbering ignored) is the template. Code then fills it: the template company's name becomes the issuer's, and
every figure, date and proper name the issuer's inputs (the prompt without its precedent) do not contain becomes [●].
No model is involved, so B2 cannot invent a figure; what it lacks is the issuer's own content.

    python -m evaluate.template [--out drive/runs/B2/predictions_test.jsonl]
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

from data.facts import RE_DATES, RE_FIG, _num, figures, parse_dates, proper_names
from evaluate.metrics import ROOT, _name_grounded, _tokens, load_rows, source_text

PH = '[●]'
DEFAULT_OUT = os.path.join(ROOT, 'drive', 'runs', 'B2', 'predictions_test.jsonl')


def _heading_words(h):
    h = re.sub(r'^\s*[\dIVXivx]+[.)]\s*', '', h or '')
    return {w for w in re.findall(r'[a-z]{3,}', h.lower())}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def build_index(train_rows):
    idx = defaultdict(list)
    for r in train_rows:
        md = r['metadata']
        if md['skill'] == 'drafting':
            idx[md['section_bucket']].append((_heading_words(md['heading']), r))
    return idx


def pick_template(row, idx):
    md = row['metadata']
    words = _heading_words(md['heading'])
    cands = [(w, r) for w, r in idx.get(md['section_bucket'], []) if r['metadata']['doc_id'] != md['doc_id']]
    if not cands:
        return None
    return max(cands, key=lambda c: (_jaccard(words, c[0]), -len(c[1]['messages'][-1]['content'])))[1]


def _company_variants(name):
    name = (name or '').strip()
    out = {name}
    short = re.sub(r'\s+(?:private\s+)?limited\.?$|\s+ltd\.?$', '', name, flags=re.I).strip()
    if len(short) > 3:
        out.add(short)
    return sorted((v for v in out if v), key=len, reverse=True)


def fill(template_text, template_company, row):
    """The template text with the issuer's name in and everything unsupported by the issuer's inputs masked."""
    text = template_text
    issuer = row['metadata']['company']
    for v in _company_variants(template_company):
        text = re.sub(re.escape(v), issuer, text, flags=re.I)
    src = source_text(row)
    src_figs, src_dates = figures(src), parse_dates(src)
    src_words = set(_tokens(src))

    # names first: masking a word such as "Regulations" can turn "Regulations 197" into a bare figure, which the
    # figure pass below then masks too
    for _ in range(3):                             # masking one name can expose a shorter one ("Mohammad Alam" -> "Alam")
        bad_names = [n for n in proper_names(text) if not _name_grounded(n, src_words)]
        if not bad_names:
            break
        for name in sorted(bad_names, key=len, reverse=True):
            words = [w for w in _tokens(name) if w not in src_words] or _tokens(name)
            for w in words:                        # only the issuer-foreign words: "Mr. [●]", not "[●] [●]"
                text = re.sub(r'(?i)\b' + re.escape(w) + r'\b', PH, text)

    def date_sub(m):
        found = parse_dates(m.group(0))
        return m.group(0) if found and found <= src_dates else PH
    for rx in RE_DATES:
        text = rx.sub(date_sub, text)

    bad = figures(text) - src_figs                 # figures() skips years, list numbers and references
    if bad:
        def fig_sub(m):                            # match on values: list numbers and years keep their value out of `bad`
            k = _num(m.group(0).strip('()').rstrip(','))
            return PH if k is not None and abs(k) in bad else m.group(0)
        text = RE_FIG.sub(fig_sub, text)
    return re.sub(r'(?:\[●\][\s-]*){2,}', PH + ' ', text).strip()


def build(test_rows, train_rows):
    idx = build_index(train_rows)
    out = []
    for row in test_rows:
        md = row['metadata']
        if md['skill'] != 'drafting':
            continue
        t = pick_template(row, idx)
        if t is None:
            pred, src_id = PH, None
        else:
            pred, src_id = fill(t['messages'][-1]['content'], t['metadata']['company'], row), t['id']
        out.append({'id': row['id'], 'metadata': md, 'prediction': pred, 'finish': 'stop', 'template_id': src_id})
    return out


def main():
    args = sys.argv[1:]
    dest = args[args.index('--out') + 1] if '--out' in args else DEFAULT_OUT
    test = list(load_rows('test.jsonl').values())
    train = list(load_rows('train.jsonl').values())
    preds = build(test, train)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as fh:
        for p in preds:
            fh.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(f'B2 template: {len(preds)} drafts written to {dest}')


if __name__ == '__main__':
    main()
