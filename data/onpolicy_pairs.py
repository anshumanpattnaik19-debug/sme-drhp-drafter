"""On-policy preference pairs for the drafting step (20 Nov 2026, run 14).

    python -m data.onpolicy_pairs prompts  [--train trainset/out/train_v3.jsonl] [--out trainset/out/train_app.jsonl]
    python -m data.onpolicy_pairs pairs    --cands drive/runs/live/qa3/onpolicy/bon_A_qa3.jsonl [--out trainset/out/onpolicy_pairs.jsonl]

Why. Pairs made from the gold text (loop pairs) or from blanking a value (abstention, keep pairs) taught the wrong thing: one made
the model write [●] for facts it held (1,242 placeholders for 47 gaps), the next over-corrected (fact use 0.80, 8% flagged). The
measures that matter are those the app applies, so the preference is built from them: the model drafts several times from the
app's own prompt, each draft goes through the guard (draft.writer.guard_draft), and the pair is the best and the worst draft by

    utility = facts stated  - 1.5 x values the guard masked  - 0.5 x placeholders beyond the gaps the prompt names
              - 5 if the draft loops  - 3 if its length is outside 0.5 to 1.6 times the filed text

A pair needs a utility gap of 3 or more. Facts stated counts the prompt's own fact values found in the draft, so a draft that
hides facts behind [●] loses what one that uses them gains, and a draft that states a value the prompt lacks loses 1.5 for each.
"""
from __future__ import annotations

import argparse
import json
import re

PH = "[●]"
RE_PRECEDENT = re.compile(r"\nPRECEDENT \(.*?(?=\nDraft the sub-section now\.|\Z)", re.S)


def prompts(train_path, out_path):
    """The drafting rows of the training set in the app's prompt format: no PRECEDENT, unknown and computed facts added."""
    from evaluate.live_eval import build_messages
    n = 0
    with open(train_path, encoding="utf-8") as src, open(out_path, "w", encoding="utf-8") as out:
        for line in src:
            r = json.loads(line) if line.strip() else None
            if not r or r["metadata"]["skill"] != "drafting":
                continue
            msgs, _ = build_messages(r, fixed=True)
            row = {"id": r["id"], "messages": [msgs[0], msgs[1], r["messages"][-1]], "metadata": r["metadata"]}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return {"prompts": n}


def utility(text, row):
    """(utility, parts) of one draft for one app-format row."""
    from evaluate.live_eval import guard_flat, prompt_parts
    _, _, facts, *_ = prompt_parts(row)
    g, masked, looped, _ = guard_flat(text, row)
    low = g.lower()
    gold = row["messages"][-1]["content"]
    used = sum(str(f["value"]).lower() in low for f in facts if len(str(f["value"])) >= 3 and str(f["value"]) != PH)
    gaps = sum(f["value"] == PH for f in facts) + gold.count(PH)
    extra_ph = max(0, text.count(PH) - gaps - 2)
    ratio = len(g) / max(1, len(gold))
    out_of_range = not 0.5 <= ratio <= 1.6
    u = used - 1.5 * masked - 0.5 * extra_ph - 5 * bool(looped) - 3 * out_of_range
    return u, dict(used=used, masked=masked, extra_ph=extra_ph, looped=bool(looped), ratio=round(ratio, 2))


def pairs(cands_path, out_path, rows_path="trainset/out/train_app.jsonl", min_gap=3.0):
    rows = {r["id"]: r for r in (json.loads(l) for l in open(rows_path, encoding="utf-8") if l.strip())}
    n_rows = n_pairs = 0
    stats = {"chosen_masked": 0, "rejected_masked": 0, "chosen_used": 0, "rejected_used": 0}
    with open(out_path, "w", encoding="utf-8") as out:
        for line in open(cands_path, encoding="utf-8"):
            if not line.strip():
                continue
            c = json.loads(line)
            row = rows.get(c["id"])
            if row is None:
                continue
            n_rows += 1
            texts = [t for t in c["candidates"] if t and t.strip()]
            if len(texts) < 2:
                continue
            scored = sorted(((*utility(t, row), t) for t in texts), key=lambda x: x[0])
            (u_lo, p_lo, worst), (u_hi, p_hi, best) = scored[0], scored[-1]
            if u_hi - u_lo < min_gap or best == worst:
                continue
            prompt = row["messages"][:-1]
            n_tok = int(sum(len(m["content"]) for m in prompt) / 3.2 + (len(best) + len(worst)) / 6.4)
            out.write(json.dumps({"id": c["id"] + "-op", "prompt": prompt, "chosen": [{"role": "assistant", "content": best}],
                                  "rejected": [{"role": "assistant", "content": worst}], "n_tokens": n_tok,
                                  "u": [round(u_hi, 1), round(u_lo, 1)]}, ensure_ascii=False) + "\n")
            n_pairs += 1
            stats["chosen_masked"] += p_hi["masked"]; stats["rejected_masked"] += p_lo["masked"]
            stats["chosen_used"] += p_hi["used"]; stats["rejected_used"] += p_lo["used"]
    k = max(1, n_pairs)
    return {"rows": n_rows, "pairs": n_pairs, **{key: round(v / k, 2) for key, v in stats.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prompts", "pairs"])
    ap.add_argument("--train", default="trainset/out/train_v3.jsonl")
    ap.add_argument("--out")
    ap.add_argument("--cands")
    ap.add_argument("--min-gap", type=float, default=3.0)
    a = ap.parse_args()
    if a.mode == "prompts":
        print(prompts(a.train, a.out or "trainset/out/train_app.jsonl"))
    else:
        print(pairs(a.cands, a.out or "trainset/out/onpolicy_pairs.jsonl", min_gap=a.min_gap))
