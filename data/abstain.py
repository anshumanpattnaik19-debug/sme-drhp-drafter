"""Training rows that show the model a gap (the 19 Nov 2026 fix plan, phase 2).

    python -m data.abstain [--train trainset/out/train_v2.jsonl] [--out trainset/out/train_v3.jsonl]
                           [--pairs trainset/out/abstain_pairs.jsonl] [--share 0.5] [--seed 7]

Why. The system prompt of every drafting row says "where FACTS do not give a detail, write [●] and do not guess", but the
rows never show it: the gates require every figure, date and name of a target to be in its prompt (2.3% of the 657 drafting
targets break that), and the 5% of targets that carry a [●] almost all hide offer terms that DRHP stage masks. The model is
trained on oracle facts and then, in the app, gets about half of them (router recall 0.48). Given a gap it has never seen
filled with [●], it fills it with a plausible value: 33% of drafts, 47% of the invented figures being address parts and
counts.

What. For a share of the drafting rows, 1 to 3 facts that the target states are removed from FACTS and every occurrence of
their value in the target becomes [●]. The row is added next to the original, so the model sees the same passage with and
without the fact. For the preference step each variant also gives a pair: chosen = the target with [●], rejected = the
original target, which states a value the prompt no longer holds (an invented figure by construction).

Also: in 60% of drafting rows (the originals and the variants) the PRECEDENT block is removed. The app sends none; half of
the rows carried one.
"""
from __future__ import annotations

import argparse
import json
import random
import re

PH = "[●]"
ELIGIBLE = {"amount", "percent", "date", "count", "place", "person", "entity", "short_text"}
RE_PRECEDENT = re.compile(r"\nPRECEDENT \(.*?(?=\nDraft the sub-section now\.|\Z)", re.S)
RE_FACTS = re.compile(r"^FACTS: (\[.*?\])\s*$", re.M)
OFFER_TERMS = re.compile(r"price|issue size|offer size|lot size|opening|closing|proceeds", re.I)


def facts_of(row):
    m = RE_FACTS.search(row["messages"][1]["content"])
    try:
        return json.loads(m.group(1)) if m else []
    except ValueError:
        return []


def _pattern(value):
    v = str(value).strip()
    return re.compile(r"(?<![\w.,])" + re.escape(v) + r"(?![\w]|[.,]\d)")


def eligible_own(row):
    """Facts of the row whose value the target states exactly, at least once, and that are safe to blank."""
    target = row["messages"][-1]["content"]
    out = []
    for f in facts_of(row):
        v = str(f.get("value", "")).strip()
        if f.get("type") not in ELIGIBLE or len(v) < 3 or v == PH or OFFER_TERMS.search(str(f.get("label", ""))):
            continue
        if f.get("type") == "short_text" and len(v.split()) > 6:              # a phrase, not a value: leave the sentence whole
            continue
        if _pattern(v).search(target):
            out.append(f)
    return out


def drop_facts(row, rng, k_max=3):
    """A copy of the row with 1..k_max own facts removed from FACTS and blanked in the target; None if nothing can be dropped."""
    own = eligible_own(row)
    if not own:
        return None
    k = min(len(own), rng.randint(1, k_max))
    chosen = rng.sample(own, k)
    target = row["messages"][-1]["content"]
    new_target = target
    for f in chosen:
        new_target = _pattern(f["value"]).sub(PH, new_target)
    if new_target == target or PH + PH in new_target.replace(" ", ""):
        return None
    gone = {id(f) for f in chosen}
    rest = [f for f in facts_of(row) if id(f) not in gone and not any(f is c for c in chosen)]
    rest = [f for f in rest if not any(f == c for c in chosen)]
    lines = [{key: f[key] for key in ("type", "label", "value", "unit", "period") if f.get(key)} for f in rest[:60]]
    facts_line = "FACTS: " + json.dumps(lines, ensure_ascii=False, separators=(",", ":"))
    user = RE_FACTS.sub(lambda m: facts_line, row["messages"][1]["content"], count=1)
    out = json.loads(json.dumps(row))
    out["messages"][1]["content"] = user
    out["messages"][-1]["content"] = new_target
    meta = out.setdefault("metadata", {})
    meta.update(variant="abstain", dropped=[f.get("label", "") for f in chosen], n_facts=len(rest),
                n_own=max(0, meta.get("n_own", len(own)) - len(chosen)))
    meta["unit_id"] = f"{meta.get('unit_id', row.get('id', ''))}-abs"
    if "id" in out:
        out["id"] = f"{out['id']}-abs"
    return out


def build(train_path, out_path, pairs_path, share=0.5, seed=7, drop_precedent=0.6):
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(train_path, encoding="utf-8") if l.strip()]
    drafting = [r for r in rows if r["metadata"]["skill"] == "drafting"]
    pick = set(id(r) for r in rng.sample(drafting, int(len(drafting) * share)))
    out, pairs, variants = [], [], 0
    for r in rows:
        out.append(r)
        if id(r) not in pick:
            continue
        v = drop_facts(r, rng)
        if v is None:
            continue
        variants += 1
        out.append(v)
        pairs.append({"id": v.get("id", ""), "prompt": v["messages"][:-1],      # the format of vm/dpo_pairs.py: one-message lists
                      "chosen": [{"role": "assistant", "content": v["messages"][-1]["content"]}],
                      "rejected": [{"role": "assistant", "content": r["messages"][-1]["content"]}], "n_tokens": 0})
    stripped = 0
    for r in out:
        if r["metadata"]["skill"] == "drafting" and RE_PRECEDENT.search(r["messages"][1]["content"]) and rng.random() < drop_precedent:
            r["messages"][1]["content"] = RE_PRECEDENT.sub("", r["messages"][1]["content"])
            r["metadata"]["precedent"] = False
            stripped += 1
    for p in pairs:                                                     # the pairs share the precedent-free prompt of their row
        p["prompt"] = [dict(m) for m in p["prompt"]]
        p["prompt"][1]["content"] = RE_PRECEDENT.sub("", p["prompt"][1]["content"]) if rng.random() < drop_precedent else p["prompt"][1]["content"]
        p["n_tokens"] = int(sum(len(m["content"]) for m in p["prompt"]) / 3.2
                            + (len(p["chosen"][0]["content"]) + len(p["rejected"][0]["content"])) / 6.4)
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(pairs_path, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    return {"rows_in": len(rows), "rows_out": len(out), "abstain_variants": variants, "pairs": len(pairs), "precedent_removed": stripped}


def keep_pairs(train_path, out_path, share=0.5, seed=11, drop_precedent=0.6):
    """The mirror of the abstention pairs: the fact IS in FACTS, chosen = the target that states it, rejected = the same target with
    the value blanked to [●]. Without these a preference step teaches 'always prefer [●]' (run A_qa3_dpo wrote 1,242 placeholders
    for the 47 gaps its 89 test prompts held and used 43% of the facts it was given)."""
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(train_path, encoding="utf-8") if l.strip()]
    drafting = [r for r in rows if r["metadata"]["skill"] == "drafting"]
    pairs = []
    for r in rng.sample(drafting, int(len(drafting) * share)):
        v = drop_facts(r, rng)
        if v is None:
            continue
        prompt = [dict(m) for m in r["messages"][:-1]]
        if rng.random() < drop_precedent:
            prompt[1]["content"] = RE_PRECEDENT.sub("", prompt[1]["content"])
        p = {"id": f"{r.get('id', '')}-keep", "prompt": prompt,
             "chosen": [{"role": "assistant", "content": r["messages"][-1]["content"]}],
             "rejected": [{"role": "assistant", "content": v["messages"][-1]["content"]}], "n_tokens": 0}
        p["n_tokens"] = int(sum(len(m["content"]) for m in prompt) / 3.2
                            + (len(p["chosen"][0]["content"]) + len(p["rejected"][0]["content"])) / 6.4)
        pairs.append(p)
    with open(out_path, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    return {"keep_pairs": len(pairs)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="trainset/out/train_v2.jsonl")
    ap.add_argument("--out", default="trainset/out/train_v3.jsonl")
    ap.add_argument("--pairs", default="trainset/out/abstain_pairs.jsonl")
    ap.add_argument("--share", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    print(build(a.train, a.out, a.pairs, a.share, a.seed))
    keep_path = a.pairs.replace("abstain_pairs", "keep_pairs")
    if keep_path != a.pairs:                       # never write the keep pairs over the abstention pairs
        print(keep_pairs(a.train, keep_path))
