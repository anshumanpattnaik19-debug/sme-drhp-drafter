"""DPO pairs against looping for run A_qa (the VM port of notebook cell 21). The adapter drafts 400 training drafting
prompts greedily; each draft that loops or hits the cap becomes the 'rejected' text (cut at rej-max tokens), the gold
sub-section the 'chosen' text. Pairs longer than pair-max tokens are skipped. Runs on the vLLM environment (~/venv-teacher).

    python vm/dpo_pairs.py --adapter ~/checkpoints/A_qa-51/adapter --train trainset/out/train_v2.jsonl --out pairs.jsonl
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())            # run from ~/sme: the data package lives there

from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import trim_repeats  # noqa: E402

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--train", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=400)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--cap", type=int, default=2200)
ap.add_argument("--rej-max", type=int, default=1200)
ap.add_argument("--pair-max", type=int, default=4096)
a = ap.parse_args()

tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
rows = [json.loads(line) for line in open(a.train, encoding="utf-8") if line.strip()]
rows = [r for r in rows if r["metadata"]["skill"] == "drafting"]
random.Random(a.seed).shuffle(rows)
rows = rows[:a.n]
prompts = [tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True) for r in rows]

llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=6144, gpu_memory_utilization=0.9)
outs = llm.generate(prompts, SamplingParams(temperature=0, max_tokens=a.cap),
                    lora_request=LoRARequest("src", 1, os.path.expanduser(a.adapter)))

pairs, n_bad, n_long = [], 0, 0
for r, prompt, o in zip(rows, prompts, outs):
    ids = list(o.outputs[0].token_ids)
    _, cut = trim_repeats(tok.decode(ids, skip_special_tokens=True))
    if not (cut or o.outputs[0].finish_reason == "length"):
        continue
    n_bad += 1
    chosen = r["messages"][-1]["content"]
    rejected = tok.decode(ids[:a.rej_max], skip_special_tokens=True)
    n_prompt = len(tok(prompt, add_special_tokens=False).input_ids)
    n_comp = max(len(tok(chosen, add_special_tokens=False).input_ids), len(tok(rejected, add_special_tokens=False).input_ids))
    if n_prompt + n_comp + 8 > a.pair_max:
        n_long += 1
        continue
    pairs.append({"id": r["id"], "prompt": r["messages"][:-1],
                  "chosen": [{"role": "assistant", "content": chosen}],
                  "rejected": [{"role": "assistant", "content": rejected}],
                  "n_tokens": n_prompt + n_comp})

with open(os.path.expanduser(a.out), "w", encoding="utf-8") as fh:
    for p in pairs:
        fh.write(json.dumps(p, ensure_ascii=False) + "\n")
print(f"{len(rows)} drafts: {n_bad} looped or hit the cap, {n_long} too long -> {len(pairs)} pairs -> {a.out}", flush=True)
assert len(pairs) >= 60, "too few pairs for DPO"
print("PAIRS_DONE", flush=True)
