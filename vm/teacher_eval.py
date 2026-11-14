"""Teacher baseline B3 (2-shot, Qwen3-32B-AWQ) and the LLM-as-judge pass, on the course VM.

B3: the teacher answers the drafting and extraction rows of test.jsonl with two short training examples in the prompt
    (the same shot selection as the B1 baseline in vm/rag_eval.py). Thinking is off.
Judge: the teacher scores each drafted sub-section against the issuer's FACTS and the sub-heading, on four 1-5 criteria:
    completeness, regulatory tone, no invention, structure. Systems judged: each drafting prediction file given on the
    command line, plus the filed text itself as the reference ('filed').

    python vm/teacher_eval.py --test trainset/out/test_v2.jsonl --train trainset/out/train_v2.jsonl --eval ~/sme/eval
"""
import argparse
import json
import os
import random
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.getcwd())

from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402

from data.prompts import trim_repeats  # noqa: E402

BASE = os.path.expanduser("~/models/Qwen3-32B-AWQ")     # downloaded by vm/setup_teacher.sh
MAX_PROMPT = 7000
JUDGE_SYSTEM = (
    "You are a senior reviewer of Indian SME Draft Red Herring Prospectuses (SEBI ICDR Chapter IX). You score one drafted "
    "sub-section. Reply with JSON only: {\"completeness\": n, \"regulatory_tone\": n, \"no_invention\": n, \"structure\": n}, "
    "each n an integer 1 to 5. completeness: the sub-heading's content is covered from the FACTS. regulatory_tone: formal, "
    "third person, offer-document style. no_invention: every figure, date and name is in the FACTS or is a [●] placeholder "
    "(5 = none invented, 1 = many invented). structure: sensible headings, paragraphs and tables for a DRHP sub-section.")


def fact_user(row):
    return row["messages"][1]["content"]


def shot_pool(train):
    pool = defaultdict(list)
    for r in train:
        if r["metadata"]["skill"] in ("drafting", "extraction") and r["metadata"].get("n_tokens_est", 0) <= 1200:
            pool[(r["metadata"]["skill"], r["metadata"].get("section_bucket"))].append(r)
    return pool


def two_shot(row, pool):
    skill = row["metadata"]["skill"]
    cands = pool.get((skill, row["metadata"].get("section_bucket"))) or [x for k, v in pool.items() if k[0] == skill for x in v]
    shots = random.Random(zlib.crc32(row["id"].encode())).sample(cands, min(2, len(cands)))
    while True:
        msgs = [row["messages"][0]]
        for s in shots:
            msgs += [s["messages"][1], s["messages"][2]]
        msgs.append(row["messages"][1])
        yield msgs, [s["id"] for s in shots]
        if not shots:
            return
        shots = shots[:-1]


def read(path):
    return [json.loads(l) for l in open(os.path.expanduser(path), encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--eval", required=True)
    ap.add_argument("--judge", nargs="*", default=[], help="NAME=predictions.jsonl (drafting predictions to judge)")
    a = ap.parse_args()
    out = Path(os.path.expanduser(a.eval))
    out.mkdir(parents=True, exist_ok=True)

    test = read(a.test)
    train = read(a.train)
    tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
    llm = LLM(BASE, quantization="awq_marlin", max_model_len=10240, gpu_memory_utilization=0.9)
    think_off = {"enable_thinking": False}

    def render(msgs):
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **think_off)

    # ---------- B3 ----------
    pool = shot_pool(train)
    rows = [r for r in test if r["metadata"]["skill"] in ("drafting", "extraction")]
    prompts, params, shots_used = [], [], []
    for r in rows:
        for msgs, shots in two_shot(r, pool):
            text = render(msgs)
            if len(tok(text, add_special_tokens=False).input_ids) <= MAX_PROMPT or not shots:
                break
        prompts.append(text)
        shots_used.append(shots)
        skill = r["metadata"]["skill"]
        params.append(SamplingParams(temperature=0, frequency_penalty=0.3 if skill == "drafting" else 0.0,
                                     max_tokens=2200 if skill == "drafting" else 3000))
    outs = [o.outputs[0] for o in llm.generate(prompts, params)]
    with open(out / "predictions_B3_teacher2shot.jsonl", "w", encoding="utf-8") as fh:
        for r, o, shots in zip(rows, outs, shots_used):
            raw = o.text
            pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
            fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                                 "finish": o.finish_reason, "loop_trimmed": cut, "shots": shots}, ensure_ascii=False) + "\n")
    print(f"B3: {len(rows)} rows", flush=True)

    # ---------- judge ----------
    systems = [("filed", None)] + [tuple(s.split("=", 1)) for s in a.judge]
    by_id = {r["id"]: r for r in test}
    judge_prompts, judge_keys = [], []
    for name, path in systems:
        if name == "filed":
            items = [(r["id"], r["messages"][-1]["content"]) for r in test if r["metadata"]["skill"] == "drafting"]
        else:
            items = []
            for p in read(path):
                if p["metadata"]["skill"] == "drafting":
                    items.append((p["id"], trim_repeats(p.get("raw", p["prediction"]))[0]))
        for rid, text in items:
            r = by_id[rid]
            heading = r["metadata"].get("heading") or ""
            facts_line = next(l for l in fact_user(r).split("\n") if l.startswith("FACTS: "))
            user = f"SUB-HEADING: {heading}\n\n{facts_line}\n\nDRAFTED SUB-SECTION:\n{text[:9000]}"
            msgs = [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]
            judge_prompts.append(render(msgs))
            judge_keys.append((name, rid))
    jouts = [o.outputs[0].text for o in llm.generate(judge_prompts, SamplingParams(temperature=0, max_tokens=120))]
    scores = []
    for (name, rid), text in zip(judge_keys, jouts):
        clean = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        m = re.search(r"\{.*\}", clean, re.S)
        try:
            d = json.loads(m.group(0))
            vals = {k: float(d[k]) for k in ("completeness", "regulatory_tone", "no_invention", "structure")}
        except Exception:  # noqa: BLE001
            vals = None
        scores.append({"system": name, "id": rid, "scores": vals, "raw": text[:200]})
    with open(out / "judge_scores.jsonl", "w", encoding="utf-8") as fh:
        for s in scores:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print("JUDGE_DONE", len(scores), flush=True)
    print("TEACHER_EVAL_DONE", flush=True)


if __name__ == "__main__":
    main()
