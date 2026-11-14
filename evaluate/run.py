"""Score prediction files, bootstrap them by company and write the evaluation report (PLAN.md section 7).

    python -m evaluate.run B0=drive/runs/B0/predictions_test_f03.jsonl B2=drive/runs/B2/predictions_test.jsonl \
        A_dpo=drive/runs/A_dpo/predictions_test_f03.jsonl --system A_dpo --compare B0 B2 [--r0 NAME] [--out evaluate/out]

--system names the system the success criteria are judged on (F2 in the plan; until F2 is run, the best fine-tuned
system stands in and the report says so). --compare lists the systems it is paired against. --r0 names the base + RAG
file for H1 when it exists. Writes REPORT.md and scores.json to --out.
"""
from __future__ import annotations

import json
import os
import sys
import time

from evaluate.metrics import ROOT, score_file
from evaluate.stats import N_BOOT, bootstrap, paired

SHOWN = ['grounding', 'grounding_figures', 'invented_fig_rate', 'invented_date_rate', 'fact_use', 'distractor_leakage',
         'rouge_l', 'loop_rate', 'len_ratio', 'extract_precision', 'extract_recall', 'extract_f1', 'json_valid']


def _ci(t):
    v, lo, hi = t
    if v is None:
        return '–'
    return f'{v:.3f} [{lo:.3f}, {hi:.3f}]' if lo is not None else f'{v:.3f}'


def criteria(boot, pairs, system, r0):
    """H1-H5 (PLAN.md 7.4) as far as the inputs allow: (id, status, evidence)."""
    s = boot[system]
    g, lo_g, _ = s['grounding']
    if r0 and r0 in boot:
        _, _, hi_r0 = boot[r0]['grounding']
        ok = g >= 0.98 and lo_g > hi_r0
        h1 = ('pass' if ok else 'fail', f'grounding {_ci(s["grounding"])} against R0 {_ci(boot[r0]["grounding"])}; needs >= 0.98 and non-overlapping intervals')
    else:
        h1 = ('fail' if g < 0.98 else 'partly met', f'grounding {_ci(s["grounding"])} (needs >= 0.98); R0 (base + RAG) not run, so the interval comparison is pending')
    inv = s['invented_fig_rate'][0]
    h2 = ('pass' if inv <= 0.02 else 'fail', f'invented-figure rate {_ci(s["invented_fig_rate"])} of drafts (needs <= 0.02)')
    h3 = ('pending', 'checklist coverage needs the reviewer\'s mandatory-item checklist (draft/outline.py holds placeholders) '
                     'and whole-section drafts; test rows are single sub-sections')
    b2 = pairs.get('B2')
    note = f"; meanwhile ROUGE-L against the filed text, {system} - B2 = {b2['rouge_l'][0]:+.3f} [{b2['rouge_l'][1]:+.3f}, {b2['rouge_l'][2]:+.3f}], p = {b2['rouge_l'][3]:.3f}" if b2 and b2['rouge_l'][0] is not None else ''
    h4 = ('pending', 'needs the LLM judge scores and the reviewer\'s blind comparison' + note)
    h5 = ('pending', 'needs the 5 issuer bundles run end to end (one, Ashtavira, exists)')
    return [('H1', *h1), ('H2', *h2), ('H3', *h3), ('H4', *h4), ('H5', *h5)]


def report(files, records, boot, pairs, system, r0, dest):
    n_draft = sum(r['skill'] == 'drafting' for r in records[system])
    n_ext = sum(r['skill'] == 'extraction' for r in records[system])
    n_co = len({r['company'] for r in records[system]})
    L = ['# Evaluation report', '',
         f'Built {time.strftime("%d %b %Y %H:%M")} by `python -m evaluate.run`. Test rows: {n_draft} drafting and {n_ext} extraction '
         f'from {n_co} companies. 95% intervals: percentile bootstrap over companies, {N_BOOT} resamples.', '',
         f'System judged against the success criteria: **{system}**. '
         + ('' if system.startswith('F2') else 'The plan judges F2 (fine-tuned + RAG); until F2 is run, this system stands in.'), '',
         '## Success criteria (PLAN.md 7.4)', '', '| | status | evidence |', '|---|---|---|']
    L += [f'| {h} | {st} | {ev} |' for h, st, ev in criteria(boot, pairs, system, r0)]
    L += ['', '## Systems', '', 'Drafting: grounding = figures, dates and names in the draft found in the issuer\'s inputs (the prompt '
          'without its precedent); invented rates = share of drafts with at least one figure / date not in those inputs; '
          'fact use = share of the facts that the filed text uses which the draft also uses; distractor leakage = share of '
          'drafts using a fact the filed text does not use. Extraction: value-level precision, recall and F1.', '']
    head = ['system', 'file'] + SHOWN
    L += ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for name, path in files.items():
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        L.append(f'| {name} | `{rel}` | ' + ' | '.join(_ci(boot[name][m]) for m in SHOWN) + ' |')
    if pairs:
        L += ['', f'## Paired differences: {system} minus each system', '',
              'Same test rows, companies resampled together; p is two-sided.', '']
        head = ['against'] + [m for m in SHOWN if m != 'len_ratio']
        L += ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
        for other, d in pairs.items():
            cells = []
            for m in head[1:]:
                v, lo, hi, p = d[m]
                cells.append('–' if v is None else f'{v:+.3f} [{lo:+.3f}, {hi:+.3f}] p={p:.3f}')
            L.append(f'| {other} | ' + ' | '.join(cells) + ' |')
    L += ['', '## Known limits', '',
          '* Figures follow `data.facts.figures`: years, page and legal references and list numbers at a line start are not '
          'figures, but list numbers inside a flattened table ("9. ... 10. Spouse Sister(s)") are, which is why B2, '
          'which cannot invent a figure, still shows a small invented-figure rate. Names follow `data.facts.proper_names`, so capitalised terms can count as names.',
          '* Checklist coverage, BERTScore and the LLM judge are not computed here yet.', '']
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, 'REPORT.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))
    out = {'system': system, 'files': {k: os.path.relpath(v, ROOT).replace(os.sep, '/') for k, v in files.items()},
           'bootstrap': {n: {m: list(t) for m, t in b.items()} for n, b in boot.items()},
           'paired': {n: {m: list(t) for m, t in d.items()} for n, d in pairs.items()},
           'criteria': [list(c) for c in criteria(boot, pairs, system, r0)]}
    with open(os.path.join(dest, 'scores.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    opts = {'--system': None, '--r0': None, '--out': os.path.join(ROOT, 'evaluate', 'out')}
    compare = []
    files = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a in opts:
            opts[a] = args[i + 1]; i += 2
        elif a == '--compare':
            i += 1
            while i < len(args) and not args[i].startswith('--') and '=' not in args[i]:
                compare.append(args[i]); i += 1
        else:
            name, path = a.split('=', 1)
            files[name] = path if os.path.isabs(path) else os.path.join(ROOT, path)
            i += 1
    system = opts['--system'] or list(files)[-1]
    records = {n: score_file(p) for n, p in files.items()}
    boot = {n: bootstrap(r) for n, r in records.items()}
    pairs = {c: paired(records[system], records[c]) for c in compare if c in records and c != system}
    report(files, records, boot, pairs, system, opts['--r0'], opts['--out'])
    for h, st, ev in criteria(boot, pairs, system, opts['--r0']):
        print(f'{h}: {st}: {ev}')
    print(f"written: {os.path.join(opts['--out'], 'REPORT.md')} and scores.json")


if __name__ == '__main__':
    main()
