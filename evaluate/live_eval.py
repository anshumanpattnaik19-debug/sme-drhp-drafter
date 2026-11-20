"""Drafting quality on the prompts the app really sends, against the live model endpoint, before and after the invented-figure fixes.

    python -m evaluate.live_eval run  --mode app|fixed [--limit N] [--workers 6] [--out drive/runs/live/<name>.jsonl]
                                      [--model sme-drhp-7b | Qwen/Qwen2.5-7B-Instruct]   (the base model is on the same endpoint)
    python -m evaluate.live_eval score drive/runs/live/app.jsonl drive/runs/live/fixed.jsonl

The 89 drafting rows of the test set are in the training format: about half carry a PRECEDENT block, which the app never sends
(draft/writer.py calls drafting_messages without one). Mode "app" removes it and calls the endpoint as the app did before the
fixes: one draft, temperature 0.2, frequency penalty 0.3. Mode "fixed" is the app after docs/INVENTED_FIGURES_FIX_PLAN.md phase 1:
explicit [●] facts for missing slots and not-yet-known ratios (draft/slots.py, draft/derive.py), three drafts per request at
temperature 0.3, each guarded (draft/writer.guard_draft), the one with the fewest masked values kept.

score reports, for each file: drafts with an invented figure in the raw model text, values masked per draft by the verifier, drafts
with an invented figure after it, fact use before and after, loops, and the time per draft. It costs GPU time: about 90 drafts.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import sys
import time

from data.prompts import trim_repeats
from draft.derive import derive_facts
from draft.slots import unknown_facts
from draft.writer import BEST_OF_TEMPERATURE, DRAFT_FREQUENCY_PENALTY, guard_draft
from evaluate import metrics as M

RE_FACTS = re.compile(r"^FACTS: (\[.*?\])\s*$", re.M)


def drafting_rows(limit=None):
    rows = [r for r in M.load_rows("test.jsonl").values() if r.get("metadata", {}).get("skill") == "drafting"]
    return rows[:limit] if limit else rows


def _field(user, name):
    m = re.search(rf"^{name}: (.*)$", user, re.M)
    return m.group(1).strip() if m else ""


def prompt_parts(row):
    """(system, user without PRECEDENT, facts as dicts, company, section, sub-heading)."""
    user = M.RE_PRECEDENT.sub("", row["messages"][1]["content"])
    m = RE_FACTS.search(user)
    try:
        facts = json.loads(m.group(1)) if m else []
    except ValueError:
        facts = []
    return row["messages"][0]["content"], user, facts, _field(user, "COMPANY"), _field(user, "SECTION"), _field(user, "SUB-HEADING")


def build_messages(row, fixed=False):
    system, user, facts, company, section, sub = prompt_parts(row)
    extras = []
    if fixed:
        extras = unknown_facts(sub, section, facts) + derive_facts(facts, sub, section)
        lines = [{k: f[k] for k in ("type", "label", "value", "unit", "period") if f.get(k)} for f in (extras + facts)[:60]]
        facts_line = "FACTS: " + json.dumps(lines, ensure_ascii=False, separators=(",", ":"))
        user = RE_FACTS.sub(lambda m: facts_line, user, count=1)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], extras


def scored_row(row, fixed):
    """The test row with the prompt the model was actually given (no precedent; computed and unknown facts added)."""
    msgs, _ = build_messages(row, fixed)
    return {**row, "messages": [msgs[0], msgs[1], row["messages"][-1]]}


def guard_flat(text, row, extras=()):
    """(guarded text, masked values, looped, raw text after the loop cut) for one draft, as the app would show it."""
    _, user, facts, company, section, sub = prompt_parts(row)
    corpus = re.sub(r"[^a-z0-9]", "", user.lower())
    blocks, n, looped, trimmed = guard_draft(text, sub, facts + list(extras), {}, company, corpus)
    out = []
    for b in blocks:
        if b["type"] == "table":
            out.append("\n".join(" | ".join(str(c) for c in r) for r in b.get("rows", [])))
        else:
            out.append(b.get("text", ""))
    return "\n\n".join(out), n, looped, trimmed


def run(mode, limit=None, workers=6, out=None, model="sme-drhp-7b"):
    from serve import llm, runpod
    runpod.load_env_file()
    st = runpod.load_state()
    settings = {"model_url": st["model_url"], "model_name": model, "api_key": os.environ.get("RUNPOD_API_KEY", ""),
                "temperature": 0.2, "max_tokens": 2200}
    chat = llm.make_chat(settings)
    fixed = mode == "fixed"
    rows = drafting_rows(limit)
    out = out or os.path.join(M.ROOT, "drive", "runs", "live", f"{mode}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    def one(row):
        msgs, extras = build_messages(row, fixed)
        t0 = time.perf_counter()
        for attempt in range(3):
            try:
                if fixed:
                    texts, usage = chat(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY, n=3, temperature=BEST_OF_TEMPERATURE)
                else:
                    text, usage = chat(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY)
                    texts = [text]
                break
            except llm.ModelError as e:
                if attempt == 2:
                    return {"id": row["id"], "error": str(e)[:200]}
                time.sleep(15)
        scored = []
        _, _, facts_in_prompt, *_ = prompt_parts(row)
        for t in texts:
            g, n, looped, _ = guard_flat(t, row, extras)
            low = g.lower()
            used = sum(str(f["value"]).lower() in low for f in facts_in_prompt if len(str(f["value"])) >= 3 and str(f["value"]) != "[●]")
            scored.append(((looped, n, -used), t))      # the same rule as draft/writer.compose
        best = min(scored, key=lambda x: x[0])[1]
        return {"id": row["id"], "prediction": best, "candidates": texts, "seconds": round(time.perf_counter() - t0, 1),
                "usage": usage, "extras": [e["label"] for e in extras]}

    done = {}
    if os.path.exists(out):
        done = {json.loads(l)["id"]: json.loads(l) for l in open(out, encoding="utf-8") if l.strip()}
    todo = [r for r in rows if r["id"] not in done or "error" in done[r["id"]]]
    print(f"{mode}: {len(rows)} drafts, {len(todo)} to run, {workers} at a time -> {out}")
    with cf.ThreadPoolExecutor(workers) as ex, open(out, "a", encoding="utf-8") as fh:
        for i, rec in enumerate(ex.map(one, todo), 1):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"  {i}/{len(todo)} {rec['id']} {rec.get('seconds', rec.get('error'))}", flush=True)


def score(path):
    rows = M.load_rows("test.jsonl")
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if "prediction" in r and rows.get(r["id"], {}).get("metadata", {}).get("skill") == "drafting"]
    fixed = any(r.get("extras") is not None and "candidates" in r and len(r["candidates"]) > 1 for r in recs)
    agg = {"n": 0, "raw_inv": 0, "ver_inv": 0, "masked": 0, "loops": 0, "own_used_raw": 0, "own_used_ver": 0, "own_total": 0, "secs": 0.0}
    kinds = {}
    for r in recs:
        row = rows[r["id"]]
        _, extras = build_messages(row, fixed)
        srow = scored_row(row, fixed)
        raw = M.draft_record(srow, {"id": r["id"], "prediction": r["prediction"], "raw": r["prediction"]})
        g, n, looped, trimmed = guard_flat(r["prediction"], row, extras)
        ver = M.draft_record(srow, {"id": r["id"], "prediction": g, "raw": g})
        agg["n"] += 1
        agg["raw_inv"] += bool(raw["invented_figures"])
        agg["ver_inv"] += bool(ver["invented_figures"])
        agg["masked"] += n
        agg["loops"] += bool(looped or trim_repeats(r["prediction"])[1])
        agg["own_used_raw"] += raw["own_used"]
        agg["own_used_ver"] += ver["own_used"]
        agg["own_total"] += raw["own_total"]
        agg["secs"] += r.get("seconds", 0)
        _, user, facts, company, section, sub = prompt_parts(row)
        blocks = guard_draft(r["prediction"], sub, facts + list(extras), {}, company, re.sub(r"[^a-z0-9]", "", user.lower()))[0]
        for b in blocks:
            for h in b.get("masked", []):
                kinds[h["kind"]] = kinds.get(h["kind"], 0) + 1
    n = max(1, agg["n"])
    print(f"\n{path}  ({agg['n']} drafts)")
    print(f"  drafts with an invented figure, raw model text : {agg['raw_inv']:3d} = {100 * agg['raw_inv'] / n:4.1f}%")
    print(f"  drafts with an invented figure, after verifier  : {agg['ver_inv']:3d} = {100 * agg['ver_inv'] / n:4.1f}%")
    print(f"  values masked per draft                          : {agg['masked'] / n:4.2f}   {dict(sorted(kinds.items(), key=lambda x: -x[1]))}")
    print(f"  fact use raw / after verifier                    : {agg['own_used_raw'] / max(1, agg['own_total']):.3f} / {agg['own_used_ver'] / max(1, agg['own_total']):.3f}")
    print(f"  drafts with a loop                               : {100 * agg['loops'] / n:4.1f}%")
    print(f"  seconds per draft (request wall time)            : {agg['secs'] / n:4.1f}")
    return agg


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        mode = a[a.index("--mode") + 1] if "--mode" in a else "app"
        lim = int(a[a.index("--limit") + 1]) if "--limit" in a else None
        wk = int(a[a.index("--workers") + 1]) if "--workers" in a else 6
        outp = a[a.index("--out") + 1] if "--out" in a else None
        mdl = a[a.index("--model") + 1] if "--model" in a else "sme-drhp-7b"
        run(mode, lim, wk, outp, mdl)
    elif a and a[0] == "score":
        for pth in a[1:]:
            score(pth)
    else:
        print(__doc__)
