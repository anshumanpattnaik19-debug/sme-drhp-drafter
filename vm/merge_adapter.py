"""Merge the A_qa_dpo adapter into the bf16 base for serving, and check the merge before it is used.

The merged model must agree with the unmerged adapter model: same top-1 next token on most positions and small logit
differences. Run A's earlier merged model was broken (FAILURE_LOG 18), so the check is a gate, not a formality: if it
fails the script exits without writing the merged weights as 'ok'.

    python vm/merge_adapter.py --adapter ~/checkpoints/A_qa_dpo/run/adapter --test trainset/out/test_v2.jsonl --out ~/models/A_qa_dpo_merged
"""
import argparse
import json
import os
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--test", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--check", type=int, default=6)
a = ap.parse_args()

base = Path("/storage/tracka/models/base_model_path.txt").read_text().strip()
tok = AutoTokenizer.from_pretrained(base, local_files_only=True)
rows = [json.loads(l) for l in open(os.path.expanduser(a.test), encoding="utf-8") if l.strip()]
picks = [r for r in rows if r["metadata"]["skill"] in ("drafting", "qa", "extraction")][:: max(1, len(rows) // a.check)][: a.check]

model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, dtype=torch.bfloat16, device_map={"": 0})
model = PeftModel.from_pretrained(model, os.path.expanduser(a.adapter))
model.eval()

agree, total, max_diff = 0, 0, 0.0
ref_logits = []
with torch.no_grad():
    for r in picks:
        text = tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt", add_special_tokens=False).input_ids[:, -2048:].to("cuda:0")
        ref_logits.append((ids, model(input_ids=ids).logits[0, -8:].float().cpu()))

merged = model.merge_and_unload()
merged.eval()
with torch.no_grad():
    for ids, ref in ref_logits:
        got = merged(input_ids=ids).logits[0, -8:].float().cpu()
        total += ref.shape[0]
        agree += int((ref.argmax(-1) == got.argmax(-1)).sum())
        max_diff = max(max_diff, float((ref - got).abs().max()))

rate = agree / max(1, total)
print(f"merge check: top-1 agreement {agree}/{total} = {rate:.3f}, max |logit diff| {max_diff:.3f}", flush=True)
if rate < 0.95:
    print("MERGE_FAILED: not saved", flush=True)
    sys.exit(1)
out = Path(os.path.expanduser(a.out))
out.mkdir(parents=True, exist_ok=True)
merged.save_pretrained(out, safe_serialization=True, max_shard_size="5GB")
tok.save_pretrained(out)
json.dump({"adapter": a.adapter, "top1_agreement": rate, "max_logit_diff": max_diff, "checked_positions": total},
          open(out / "merge_check.json", "w"), indent=1)
print("MERGE_OK", str(out), flush=True)
