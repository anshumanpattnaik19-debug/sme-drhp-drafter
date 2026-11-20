"""Fine-tuned model against the base model, drafting, through the same verifier.

    python -m evaluate.compare_base [fine_tuned.jsonl base.jsonl]

Default files are the course-VM predictions on the 89 drafting test rows (drive/runs/A_qa/predictions_A_qa_dpo.jsonl and
predictions_base.jsonl: same prompts, same decoding). For each model it reports the raw text and the text after the app's guard
(draft/writer.guard_draft): invented figures, values masked, fact use, distractor use, ROUGE-L to the filed text, loops. Lower is
better for invented figures, masks, distractor use and loops; higher for fact use and ROUGE-L.

A model that masks fewer values but also uses fewer of the issuer's facts is not better: both columns are shown.
"""
from __future__ import annotations

import os
import sys

from data.prompts import trim_repeats
from evaluate import metrics as M
from evaluate.live_eval import guard_flat


def stats(path, rows):
    recs = [p for p in M.load_preds(path) if rows.get(p["id"], {}).get("metadata", {}).get("skill") == "drafting"]
    a = {"n": 0, "inv_raw": 0, "inv_ver": 0, "masked": 0, "own_raw": 0, "own_ver": 0, "own_tot": 0, "dis_raw": 0, "dis_ver": 0, "dis_n": 0,
         "rouge_raw": 0.0, "rouge_ver": 0.0, "loops": 0, "len_ratio": 0.0}
    for p in recs:
        row = rows[p["id"]]
        raw_text = p.get("raw", p["prediction"])
        text, cut = trim_repeats(raw_text)
        raw = M.draft_record(row, {"id": p["id"], "prediction": text, "raw": text})
        g, n, looped, _ = guard_flat(raw_text, row)
        ver = M.draft_record(row, {"id": p["id"], "prediction": g, "raw": g})
        a["n"] += 1
        a["inv_raw"] += bool(raw["invented_figures"])
        a["inv_ver"] += bool(ver["invented_figures"])
        a["masked"] += n
        a["own_raw"] += raw["own_used"]
        a["own_ver"] += ver["own_used"]
        a["own_tot"] += raw["own_total"]
        for k, rec in (("raw", raw), ("ver", ver)):
            if rec["distractor_used"] is not None:
                a[f"dis_{k}"] += bool(rec["distractor_used"])
        a["dis_n"] += raw["distractor_used"] is not None
        a["rouge_raw"] += raw["rouge_l"]
        a["rouge_ver"] += ver["rouge_l"]
        a["loops"] += bool(cut or p.get("loop_trimmed") or looped)
        a["len_ratio"] += raw["len_ratio"]
    return a


def show(name, a):
    n = max(1, a["n"])
    print(f"\n{name}  ({a['n']} drafts)")
    print(f"  invented figure, raw / after guard      : {100 * a['inv_raw'] / n:4.1f}% / {100 * a['inv_ver'] / n:4.1f}%")
    print(f"  values masked per draft                 : {a['masked'] / n:4.2f}")
    print(f"  fact use, raw / after guard             : {a['own_raw'] / max(1, a['own_tot']):.3f} / {a['own_ver'] / max(1, a['own_tot']):.3f}")
    print(f"  distractor use, raw / after guard       : {100 * a['dis_raw'] / max(1, a['dis_n']):4.1f}% / {100 * a['dis_ver'] / max(1, a['dis_n']):4.1f}%")
    print(f"  ROUGE-L to the filed text, raw / guard  : {a['rouge_raw'] / n:.3f} / {a['rouge_ver'] / n:.3f}")
    print(f"  loops                                   : {100 * a['loops'] / n:4.1f}%")
    print(f"  length against the filed text           : {a['len_ratio'] / n:.2f}")


def main(argv):
    rows = M.load_rows("test.jsonl")
    ft = argv[0] if argv else os.path.join(M.ROOT, "drive", "runs", "A_qa", "predictions_A_qa_dpo.jsonl")
    base = argv[1] if len(argv) > 1 else os.path.join(M.ROOT, "drive", "runs", "A_qa", "predictions_base.jsonl")
    show("fine-tuned", stats(ft, rows))
    show("base model", stats(base, rows))


if __name__ == "__main__":
    main(sys.argv[1:])
