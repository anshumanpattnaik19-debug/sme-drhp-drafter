"""The Responsible AI probes of rai/probes.py on the course VM with vLLM (no endpoint): the base model and any number of adapters,
greedy, max 300 tokens; the consistency probes as 3 samples at temperature 0.7. Output has the format of rai/probes.py, so
rai/rai_eval.py's scoring reads it.

    python vm/rai_probes_vllm.py --out ~/checkpoints/rai/rai_probes_vm.jsonl --adapter sme-drhp-7b=PATH --adapter sme-drhp-7b-rai=PATH
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from rai.probes import build  # noqa: E402

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--adapter", action="append", default=[], help="NAME=PATH")
ap.add_argument("--train", default="trainset/out/train_v3.jsonl")
a = ap.parse_args()
items = build(a.train)
llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=6144, gpu_memory_utilization=0.9, seed=11)
tok = llm.get_tokenizer()
prompts = [tok.apply_chat_template(i["messages"], tokenize=False, add_generation_prompt=True) for i in items]
params = [SamplingParams(temperature=0.7, n=3, max_tokens=300, seed=11) if i.get("samples") else
          SamplingParams(temperature=0, max_tokens=300) for i in items]
runs = [("Qwen/Qwen2.5-7B-Instruct", None)] + [(s.split("=", 1)[0], LoRARequest(s.split("=", 1)[0], k + 1,
                                                 os.path.expanduser(s.split("=", 1)[1]))) for k, s in enumerate(a.adapter)]
os.makedirs(os.path.dirname(os.path.expanduser(a.out)), exist_ok=True)
with open(os.path.expanduser(a.out), "w", encoding="utf-8") as fh:
    for name, lora in runs:
        outs = llm.generate(prompts, params, lora_request=lora)
        for it, o in zip(items, outs):
            out = [c.text for c in o.outputs] if it.get("samples") else o.outputs[0].text
            fh.write(json.dumps({**{k: v for k, v in it.items() if k != "messages"}, "model": name, "output": out, "error": None},
                                ensure_ascii=False) + "\n")
        print(f"{name}: {len(items)} probes", flush=True)
print("RAI_PROBES_DONE", flush=True)
