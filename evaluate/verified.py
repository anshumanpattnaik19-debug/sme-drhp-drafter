"""Run the verifier's masking step over a prediction file, the way the app treats model prose, and write the result
as a new prediction file the harness can score ("system = model + verifier").

The verifier's sources are the row's FACTS and the prompt's context (company, section, outline, sub-heading); the
precedent is not a source. Its detectors (verify/checks.py) are separate from the metric's (data/facts.py), so what
it misses still shows up in the scores.

    python -m evaluate.verified drive/runs/A_dpo/predictions_test_f03.jsonl [--out PATH]
    (default out: the same folder, <name>_verified.jsonl)
"""
from __future__ import annotations

import json
import os
import re
import sys

from data.prompts import trim_repeats
from evaluate.metrics import ROOT, load_rows, source_text
from verify.checks import mask_ungrounded


def facts_list(user):
    m = re.search(r'^FACTS: (\[.*?\])\s*$', user, re.M)
    try:
        return [f for f in json.loads(m.group(1)) if isinstance(f, dict) and 'value' in f]
    except Exception:
        return []


def verify_pred(row, pred):
    """The prediction with its drafting text loop-trimmed and masked; extraction rows pass through."""
    if row['metadata']['skill'] != 'drafting':
        return dict(pred)
    text, cut = trim_repeats(pred.get('raw', pred['prediction']))
    user = row['messages'][1]['content']
    context = re.sub(r'^FACTS: .*$', '', source_text(row).split('\n', 1)[-1], flags=re.M)   # company, section, outline, heading
    masked_text, masked = mask_ungrounded(text, facts_list(user), None, context)
    out = {k: v for k, v in pred.items() if k != 'raw'}
    out.update(prediction=masked_text, loop_trimmed=bool(cut or pred.get('loop_trimmed')), masked=masked)
    return out


def main():
    args = sys.argv[1:]
    src = args[0] if os.path.isabs(args[0]) else os.path.join(ROOT, args[0])
    dest = args[args.index('--out') + 1] if '--out' in args else re.sub(r'\.jsonl$', '_verified.jsonl', src)
    rows = load_rows()
    n = n_masked = 0
    with open(dest, 'w', encoding='utf-8') as fh:
        for line in open(src, encoding='utf-8'):
            p = json.loads(line)
            v = verify_pred(rows[p['id']], p)
            n += 1
            n_masked += len(v.get('masked', []))
            fh.write(json.dumps(v, ensure_ascii=False) + '\n')
    print(f'{n} predictions, {n_masked} values masked -> {dest}')


if __name__ == '__main__':
    main()
