"""AWQ 4-bit export of the deployed adapter (brief item 7: merge and quantise), with llm-compressor (compressed-tensors format,
which vLLM loads directly).

1. merge   the adapter into the bf16 base in memory; gate: the merged model must pick the same next token as base + adapter on
           at least 95% of checked positions (run A's earlier merge was broken, FAILURE_LOG 18), else nothing is written.
           The merged bf16 weights are not saved: the VM's 35 GB quota cannot hold them next to the AWQ export.
2. AWQ     W4A16 asymmetric, group 128, lm_head kept in bf16. Calibration uses training rows only, in the proportions the app
           sends them: 64 drafting prompts in the app format, 32 extraction and 32 question-answering rows, each with its
           answer, cut at 2,048 tokens.

    ~/venv-teacher/bin/python vm/quant_awq.py --adapter ~/checkpoints/A_qa3_dpo3/run/adapter --out ~/models/A_qa3_dpo3_awq
"""
import argparse
import json
import os
import random
import sys

import torch
from datasets import Dataset
from llmcompressor import oneshot
from llmcompressor.modifiers.awq import AWQModifier
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--max-len", type=int, default=2048)
ap.add_argument("--check", type=int, default=6)
a = ap.parse_args()

rng = random.Random(7)
load = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]   # noqa: E731
tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)

# 1. merge, with the agreement gate
test = load("trainset/out/test_v2.jsonl")
picks = test[:: max(1, len(test) // a.check)][: a.check]
model = AutoModelForCausalLM.from_pretrained(BASE, local_files_only=True, torch_dtype=torch.bfloat16, device_map={"": 0})
model = PeftModel.from_pretrained(model, os.path.expanduser(a.adapter))
model.eval()
refs = []
with torch.no_grad():
    for r in picks:
        text = tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt", add_special_tokens=False).input_ids[:, -2048:].to("cuda:0")
        refs.append((ids, model(input_ids=ids).logits[0, -8:].float().cpu()))
model = model.merge_and_unload()
model.eval()
agree = total = 0
max_diff = 0.0
with torch.no_grad():
    for ids, ref in refs:
        got = model(input_ids=ids).logits[0, -8:].float().cpu()
        total += ref.shape[0]
        agree += int((ref.argmax(-1) == got.argmax(-1)).sum())
        max_diff = max(max_diff, float((ref - got).abs().max()))
rate = agree / max(1, total)
print(f"merge check: top-1 agreement {agree}/{total} = {rate:.3f}, max |logit diff| {max_diff:.3f}", flush=True)
if rate < 0.95:
    print("MERGE_FAILED: nothing written", flush=True)
    sys.exit(1)

# 2. AWQ
drafting = load("trainset/out/train_app.jsonl")
other = load("trainset/out/train_v2.jsonl")
ext = [r for r in other if r["metadata"]["skill"] == "extraction"]
qa = [r for r in other if r["metadata"]["skill"] == "qa"]
share = a.samples // 4
rows = rng.sample(drafting, 2 * share) + rng.sample(ext, share) + rng.sample(qa, a.samples - 3 * share)
enc = [tok(tok.apply_chat_template(r["messages"], tokenize=False), add_special_tokens=False, truncation=True,
           max_length=a.max_len) for r in rows]
ds = Dataset.from_list([{"input_ids": e["input_ids"], "attention_mask": e["attention_mask"]} for e in enc])
print(f"calibration: {len(ds)} rows, {sum(len(e['input_ids']) for e in enc)} tokens", flush=True)

recipe = [AWQModifier(ignore=["lm_head"], scheme="W4A16_ASYM", targets=["Linear"])]
oneshot(model=model, dataset=ds, recipe=recipe, max_seq_length=a.max_len, num_calibration_samples=len(ds))

out = os.path.expanduser(a.out)
model.save_pretrained(out, save_compressed=True)
tok.save_pretrained(out)
json.dump({"base": BASE, "adapter": a.adapter, "merge_top1_agreement": rate, "merge_max_logit_diff": max_diff,
           "scheme": "W4A16_ASYM (AWQ, group 128, lm_head bf16)", "calibration_rows": len(ds),
           "calibration_mix": {"drafting": 2 * share, "extraction": share, "qa": a.samples - 3 * share}},
          open(os.path.join(out, "quant_info.json"), "w"), indent=1)
print("AWQ_OK", out, flush=True)
