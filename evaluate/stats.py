"""Aggregate metrics and bootstrap intervals by company (PLAN.md section 7.3).

Ratios are pooled over rows (micro): grounding is grounded items over all items, not a mean of per-draft shares.
Companies are the resampling unit because rows of one company share facts and style.
"""
from __future__ import annotations

import random
from collections import defaultdict

N_BOOT = 1000

# name: (skill, function of the records of that skill, higher is better)
METRICS = {
    'grounding':          ('drafting', lambda R: _ratio(R, ('figures_grounded', 'dates_grounded', 'names_grounded'), ('figures', 'dates', 'names')), True),
    'grounding_figures':  ('drafting', lambda R: _ratio(R, ('figures_grounded',), ('figures',)), True),
    'invented_fig_rate':  ('drafting', lambda R: _mean(R, 'invented_figure'), False),
    'invented_date_rate': ('drafting', lambda R: _mean(R, 'invented_date'), False),
    'fact_use':           ('drafting', lambda R: _ratio(R, ('own_used',), ('own_total',)), True),
    'distractor_leakage': ('drafting', lambda R: _mean(R, 'distractor_used'), False),
    'rouge_l':            ('drafting', lambda R: _mean(R, 'rouge_l'), True),
    'loop_rate':          ('drafting', lambda R: _mean(R, 'loop'), False),
    'len_ratio':          ('drafting', lambda R: _mean(R, 'len_ratio'), None),
    'extract_precision':  ('extraction', lambda R: _ratio(R, ('tp',), ('n_pred',)), True),
    'extract_recall':     ('extraction', lambda R: _ratio(R, ('tp',), ('n_gold',)), True),
    'extract_f1':         ('extraction', lambda R: _f1(R), True),
    'json_valid':         ('extraction', lambda R: _mean(R, 'valid'), True),
    # Q&A (data/qa.py): answer quality on answerable rows, behaviour on every row, by kind
    'qa_f1':              ('qa', lambda R: _mean([r for r in R if r['qa_type'] == 'answerable'], 'qa_f1'), True),
    'qa_cites_gold':      ('qa', lambda R: _mean([r for r in R if r['qa_type'] == 'answerable'], 'cited_gold'), True),
    'qa_grounding':       ('qa', lambda R: _ratio(R, ('qa_figures_grounded',), ('qa_figures',)), True),
    'qa_false_refusal':   ('qa', lambda R: _mean([r for r in R if r['qa_type'] == 'answerable'], 'false_refusal'), False),
    'qa_says_unknown':    ('qa', lambda R: _mean([r for r in R if r['qa_type'] == 'unanswerable'], 'behaviour_ok'), True),
    'qa_guardrails':      ('qa', lambda R: _mean([r for r in R if r['qa_type'] not in ('answerable', 'unanswerable')], 'behaviour_ok'), True),
    'qa_injection_resist': ('qa', lambda R: _mean([r for r in R if r['qa_type'] == 'injection'], 'behaviour_ok'), True),
}


def _mean(R, key):
    vals = [r[key] for r in R if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _ratio(R, num, den):
    d = sum(r.get(k, 0) for r in R for k in den)
    return sum(r.get(k, 0) for r in R for k in num) / d if d else None


def _f1(R):
    p, r = _ratio(R, ('tp',), ('n_pred',)), _ratio(R, ('tp',), ('n_gold',))
    return 2 * p * r / (p + r) if p and r else 0.0 if p is not None and r is not None else None


def by_skill(records):
    out = defaultdict(list)
    for r in records:
        out[r['skill']].append(r)
    return out


def point(records):
    sk = by_skill(records)
    return {m: fn(sk[skill]) for m, (skill, fn, _) in METRICS.items()}


def _groups(records):
    g = defaultdict(list)
    for r in records:
        g[r['company']].append(r)
    return g


def bootstrap(records, n=N_BOOT, seed=0, alpha=0.05):
    """{metric: (point, low, high)} with percentile intervals over companies resampled with replacement."""
    rng = random.Random(seed)
    groups = _groups(records)
    keys = sorted(groups)
    samples = defaultdict(list)
    for _ in range(n):
        R = [r for k in rng.choices(keys, k=len(keys)) for r in groups[k]]
        for m, v in point(R).items():
            if v is not None:
                samples[m].append(v)
    out = {}
    for m, v in point(records).items():
        s = sorted(samples[m])
        out[m] = (v, s[int(alpha / 2 * len(s))], s[min(len(s) - 1, int((1 - alpha / 2) * len(s)))]) if s and v is not None else (v, None, None)
    return out


def paired(rec_a, rec_b, n=N_BOOT, seed=0):
    """Difference a - b on the rows both systems answered, resampling companies: {metric: (diff, low, high, p)};
    p is two-sided (twice the smaller tail share of the resampled differences on either side of 0)."""
    ids = {r['id'] for r in rec_a} & {r['id'] for r in rec_b}
    A = [r for r in rec_a if r['id'] in ids]
    B = {r['id']: r for r in rec_b if r['id'] in ids}
    ga = _groups(A)
    keys = sorted(ga)
    rng = random.Random(seed)
    diffs = defaultdict(list)
    for _ in range(n):
        pick = rng.choices(keys, k=len(keys))
        Ra = [r for k in pick for r in ga[k]]
        Rb = [B[r['id']] for r in Ra]
        pa, pb = point(Ra), point(Rb)
        for m in METRICS:
            if pa[m] is not None and pb[m] is not None:
                diffs[m].append(pa[m] - pb[m])
    pa, pb = point(A), point(list(B.values()))
    out = {}
    for m in METRICS:
        s = sorted(diffs[m])
        if not s or pa[m] is None or pb[m] is None:
            out[m] = (None, None, None, None)
            continue
        le = sum(x <= 0 for x in s) / len(s)
        ge = sum(x >= 0 for x in s) / len(s)
        out[m] = (pa[m] - pb[m], s[int(0.025 * len(s))], s[min(len(s) - 1, int(0.975 * len(s)))], min(1.0, 2 * min(le, ge)))
    return out
