"""Predictions for run A_qa on the course VM, with the base model alongside: both on test_v2.jsonl (199 rows: 89 drafting,
50 extraction, 60 Q&A), with the decoding of notebook cell 17 (greedy; drafting with frequency penalty 0.3; caps 2,200 /
3,000 / 600 tokens; drafts trimmed at a loop). One vLLM engine serves both: the base model, then the base with the adapter.

    python vm/predict_qa.py --adapter ~/checkpoints/A_qa-51/adapter --test trainset/out/test_v2.jsonl --out ~/checkpoints/A_qa-51
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())            # run from ~/sme: the data package lives there, not next to this script

from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import trim_repeats  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--test", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--name", default="A_qa")
ap.add_argument("--with-base", action="store_true", help="also write the base model's predictions")
a = ap.parse_args()

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
CAP = {"drafting": 2200, "extraction": 3000, "qa": 600}
out = Path(a.out).expanduser()
out.mkdir(parents=True, exist_ok=True)

rows = [json.loads(line) for line in open(a.test, encoding="utf-8") if line.strip()]
tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
prompts = [tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True) for r in rows]
params = [SamplingParams(temperature=0, frequency_penalty=0.3 if r["metadata"]["skill"] == "drafting" else 0.0,
                         max_tokens=CAP[r["metadata"]["skill"]]) for r in rows]
llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=6144, gpu_memory_utilization=0.9)

runs = [(a.name, LoRARequest(a.name, 1, os.path.expanduser(a.adapter)))]
if a.with_base:
    runs.insert(0, ("base", None))
for name, lora in runs:
    outs = llm.generate(prompts, params, lora_request=lora)
    n_cap = n_cut = 0
    with open(out / f"predictions_{name}.jsonl", "w", encoding="utf-8") as fh:
        for r, o in zip(rows, outs):
            raw, finish = o.outputs[0].text, o.outputs[0].finish_reason
            pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
            n_cap += finish == "length"
            n_cut += cut
            fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                                 "finish": finish, "loop_trimmed": cut}, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} rows, {n_cap} hit the cap, {n_cut} drafts trimmed at a loop", flush=True)
print("PREDICTIONS_DONE", flush=True)
