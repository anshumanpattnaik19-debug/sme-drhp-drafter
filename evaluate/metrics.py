"""Per-row metrics for one prediction file against the test rows (PLAN.md section 7.2).

Every row gets its own record, so the statistics can resample by company. The source a draft may use is the prompt
without its PRECEDENT block: the precedent is another company's text, "for structure and tone only, never for figures
or names", so a figure copied from it counts as invented. (data.score_preds counts the whole prompt; its unknown-figure
numbers are therefore lower than these.)

Drafting record: loop, cap, len_ratio, figures / figures_grounded, dates / dates_grounded, names / names_grounded,
invented_figure (any figure not in the source), invented_date, own_used / own_total (fact use), distractor_used
(None when the row has no distractor), rouge_l (F1 against the filed text), placeholders.
Extraction record: valid (JSON parses), tp, n_pred, n_gold (value level, code fences stripped).
"""
from __future__ import annotations

import json
import os
import re

from data.facts import figures, parse_dates, proper_names
from data.prompts import trim_repeats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_PRECEDENT = re.compile(r"\nPRECEDENT \(.*?(?=\nDraft the sub-section now\.|\Z)", re.S)
RE_WORD = re.compile(r"\w+", re.U)
ROUGE_MAX = 1200          # tokens per side: LCS is quadratic, and a draft longer than this has failed anyway


def load_rows(name='test.jsonl'):
    path = os.path.join(ROOT, 'trainset', 'out', name)
    return {r['id']: r for r in map(json.loads, open(path, encoding='utf-8'))}


def load_preds(path):
    return [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]


def source_text(row):
    """System prompt plus user prompt, with the PRECEDENT block cut out."""
    user = RE_PRECEDENT.sub('', row['messages'][1]['content'])
    return row['messages'][0]['content'] + '\n' + user


def facts_of(user):
    m = re.search(r'^FACTS: (\[.*?\])\s*$', user, re.M)
    try:
        return [str(f['value']) for f in json.loads(m.group(1))]
    except Exception:
        return []


def _tokens(text):
    return RE_WORD.findall(text.lower())


def rouge_l(pred, gold):
    """ROUGE-L F1 on lower-cased word tokens."""
    a, b = _tokens(pred)[:ROUGE_MAX], _tokens(gold)[:ROUGE_MAX]
    if not a or not b:
        return 0.0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    lcs = prev[-1]
    if not lcs:
        return 0.0
    p, r = lcs / len(a), lcs / len(b)
    return 2 * p * r / (p + r)


def _name_grounded(name, src_words):
    """Word by word, so punctuation ("Dhurka Spouse’s", "Unit-I", "Rathi-") does not decide it."""
    return all(w in src_words for w in _tokens(name))


def draft_record(row, pred):
    raw = pred.get('raw', pred['prediction'])
    text, cut = trim_repeats(raw)
    gold = row['messages'][-1]['content']
    src = source_text(row)
    src_figs, src_dates = figures(src), parse_dates(src)
    src_words = set(_tokens(src))
    figs, dates, names = figures(text), parse_dates(text), proper_names(text)
    vals = facts_of(row['messages'][1]['content'])
    low, glow = text.lower(), gold.lower()
    own = [v for v in vals if v.lower() in glow]
    dis = [v for v in vals if v.lower() not in glow]
    return dict(
        loop=bool(cut or pred.get('loop_trimmed')), cap=pred.get('finish') == 'length',
        len_ratio=len(text) / max(1, len(gold)),
        figures=len(figs), figures_grounded=len(figs & src_figs),
        dates=len(dates), dates_grounded=len(dates & src_dates),
        names=len(names), names_grounded=sum(_name_grounded(n, src_words) for n in names),
        invented_figure=bool(figs - src_figs), invented_date=bool(dates - src_dates),
        invented_figures=sorted(figs - src_figs)[:20], invented_dates=sorted(str(d) for d in dates - src_dates)[:20],
        own_used=sum(v.lower() in low for v in own), own_total=len(own),
        distractor_used=(any(v.lower() in low for v in dis) if dis else None),
        rouge_l=rouge_l(text, gold), placeholders=text.count('[●]'))


def _parse_json(text):
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:
        obj = json.loads(t)
    except Exception:
        return None
    facts = obj.get('facts') if isinstance(obj, dict) else obj
    return facts if isinstance(facts, list) else None


def _norm(v):
    return re.sub(r'\s+', ' ', str(v)).strip().lower()


def extraction_record(row, pred):
    got = _parse_json(pred['prediction'])
    want = _parse_json(row['messages'][-1]['content']) or []
    gv = {_norm(f.get('value', '')) for f in want if isinstance(f, dict)}
    pv = {_norm(f.get('value', '')) for f in (got or []) if isinstance(f, dict)}
    return dict(valid=got is not None, tp=len(gv & pv), n_pred=len(pv), n_gold=len(gv))


def score_file(path, rows=None):
    """One record per prediction: {'id', 'company', 'section', 'skill', ...metrics}. Rows default to test.jsonl,
    or test_nopage.jsonl when every id is there and differs (run A2)."""
    preds = load_preds(path)
    if rows is None:
        rows = load_rows()
        nopage = load_rows('test_nopage.jsonl')
        if all(p['id'] in nopage for p in preds) and any(nopage[p['id']] != rows.get(p['id']) for p in preds):
            rows = nopage
    out = []
    for p in preds:
        r = rows[p['id']]
        md = r['metadata']
        rec = dict(id=p['id'], company=md['doc_id'], section=md['section_bucket'], skill=md['skill'])
        rec.update(draft_record(r, p) if md['skill'] == 'drafting' else extraction_record(r, p))
        out.append(rec)
    return out
