"""Three drafts per prompt, as the app asks for them (temperature 0.3, frequency penalty 0.3, n=3), for each adapter and the base,
on the app-format drafting prompts. Candidates are written raw; the selection rule is applied locally (evaluate/score_app.py).

    python vm/predict_bon.py --test trainset/out/test_app.jsonl --out ~/checkpoints/bon --adapter NAME=PATH [--adapter ...] [--with-base]
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--test", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--adapter", action="append", default=[], help="NAME=PATH")
ap.add_argument("--with-base", action="store_true")
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--temp", type=float, default=0.3)
ap.add_argument("--max-tokens", type=int, default=2200)
a = ap.parse_args()

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
out = Path(a.out).expanduser()
out.mkdir(parents=True, exist_ok=True)
rows = [json.loads(l) for l in open(a.test, encoding="utf-8") if l.strip()]
tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
prompts = [tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True) for r in rows]
params = SamplingParams(temperature=a.temp, frequency_penalty=0.3, max_tokens=a.max_tokens, n=a.n, seed=11)
llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=6144, gpu_memory_utilization=0.9)
runs = [(spec.split("=", 1)[0], i + 1, os.path.expanduser(spec.split("=", 1)[1])) for i, spec in enumerate(a.adapter)]
if a.with_base:
    runs.insert(0, ("base", 0, None))
for name, lid, path in runs:
    outs = llm.generate(prompts, params, lora_request=LoRARequest(name, lid, path) if path else None)
    with open(out / f"bon_{name}.jsonl", "w", encoding="utf-8") as fh:
        for r, o in zip(rows, outs):
            fh.write(json.dumps({"id": r["id"], "candidates": [c.text for c in o.outputs],
                                 "finish": [c.finish_reason for c in o.outputs]}, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} prompts x {a.n}", flush=True)
print("BON_DONE", flush=True)
