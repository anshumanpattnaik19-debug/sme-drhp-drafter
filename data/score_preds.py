"""Score prediction files on the test rows with one set of measures, so every run and decoding setting compares like
with like.

    python -m data.score_preds <name>=<predictions.jsonl> ... [--out scores.json]

Drafting (per draft, averaged): loop = trim_repeats cuts the raw text or the file says loop_trimmed; cap = finish is
'length'; len = draft chars / gold chars; own = share of FACTS values that appear in the gold sub-section and also in
the draft; distractor = share of drafts using a FACTS value that is NOT in the gold; unk_fig = figures in the draft
(data.facts.figures) found nowhere in the prompt; unk_date = the same for dates.
Extraction: value-level precision and recall against the gold JSON, code fences stripped, and JSON validity.
"""
import json
import os
import re
import sys

from data.facts import figures, parse_dates
from data.prompts import trim_repeats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TESTS = {name: {r['id']: r for r in map(json.loads, open(f'{ROOT}/trainset/out/{name}', encoding='utf-8'))}
         for name in ('test.jsonl', 'test_nopage.jsonl')}


def facts_of(user):
    m = re.search(r'^FACTS: (\[.*?\])\s*$', user, re.M)
    try:
        return [str(f['value']) for f in json.loads(m.group(1))]
    except Exception:
        return []


def norm(v):
    return re.sub(r'\s+', ' ', str(v).lower().replace(',', '')).strip()


def parse_json(text):
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:
        d = json.loads(t)
    except Exception:
        return None
    return d.get('facts', []) if isinstance(d, dict) else d if isinstance(d, list) else None


def score(path):
    preds = [json.loads(l) for l in open(path, encoding='utf-8')]
    test = TESTS['test_nopage.jsonl'] if all(p['id'] in TESTS['test_nopage.jsonl'] for p in preds) and \
        any(TESTS['test_nopage.jsonl'][p['id']] != TESTS['test.jsonl'].get(p['id']) for p in preds) else TESTS['test.jsonl']
    d = dict(n=0, loop=0, cap=0, len=0.0, own=0.0, n_own=0, dis=0, n_dis=0, unk_fig=0, unk_date=0)
    e = dict(n=0, valid=0, tp=0, n_pred=0, n_gold=0)
    for p in preds:
        r = test[p['id']]
        gold = r['messages'][-1]['content']
        prompt = r['messages'][0]['content'] + '\n' + r['messages'][1]['content']
        if r['metadata']['skill'] == 'drafting':
            raw = p.get('raw', p['prediction'])
            pred, cut = trim_repeats(raw)
            d['n'] += 1
            d['loop'] += bool(cut or p.get('loop_trimmed'))
            d['cap'] += p.get('finish') == 'length'
            d['len'] += len(pred) / max(1, len(gold))
            vals = facts_of(r['messages'][1]['content'])
            low, glow = pred.lower(), gold.lower()
            own = [v for v in vals if v.lower() in glow]
            dis = [v for v in vals if v.lower() not in glow]
            if own:
                d['own'] += sum(v.lower() in low for v in own) / len(own)
                d['n_own'] += 1
            if dis:
                d['dis'] += any(v.lower() in low for v in dis)
                d['n_dis'] += 1
            d['unk_fig'] += len(figures(pred) - figures(prompt))
            d['unk_date'] += len(parse_dates(pred) - parse_dates(prompt))
        else:
            e['n'] += 1
            got, want = parse_json(p['prediction']), parse_json(gold) or []
            if got is None:
                got = []
            else:
                e['valid'] += 1
            gv = {norm(f.get('value', '')) for f in want if isinstance(f, dict)}
            pv = {norm(f.get('value', '')) for f in got if isinstance(f, dict)}
            e['tp'] += len(gv & pv)
            e['n_pred'] += len(pv)
            e['n_gold'] += len(gv)
    return d, e


def main():
    print(f"{'file':26s} {'drafts':>6s} {'loop':>5s} {'cap':>4s} {'len':>5s} {'own':>5s} {'distr':>6s} {'unkfig':>6s} {'unkdat':>6s}"
          f" | {'extr':>4s} {'valid':>5s} {'prec':>5s} {'rec':>5s}")
    args, dest = sys.argv[1:], None
    if '--out' in args:
        i = args.index('--out'); dest = args[i + 1]; args = args[:i] + args[i + 2:]
    out = {}
    for arg in args:
        name, path = arg.split('=', 1)
        d, e = score(path)
        n = max(1, d['n'])
        row = dict(drafts=d['n'], loops=d['loop'], caps=d['cap'], len_ratio=d['len'] / n, own_fact_use=d['own'] / max(1, d['n_own']),
                   distractor_use=d['dis'] / max(1, d['n_dis']), unknown_figures=d['unk_fig'] / n, unknown_dates=d['unk_date'] / n)
        if e['n']:
            row.update(extraction=e['n'], json_valid=e['valid'], precision=e['tp'] / max(1, e['n_pred']), recall=e['tp'] / max(1, e['n_gold']))
        out[name] = row
        ex = (f"{e['n']:4d} {e['valid']:5d} {row['precision']:5.3f} {row['recall']:5.3f}" if e['n'] else f"{'-':>4s}")
        print(f"{name:26s} {d['n']:6d} {d['loop']:5d} {d['cap']:4d} {row['len_ratio']:5.2f} {row['own_fact_use']:5.3f} "
              f"{row['distractor_use']:6.3f} {row['unknown_figures']:6.2f} {row['unknown_dates']:6.2f} | {ex}")
    if dest:
        json.dump(out, open(dest, 'w'), indent=1)


if __name__ == '__main__':
    main()
