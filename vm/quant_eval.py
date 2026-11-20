"""One served model on vLLM (the bf16 base with the adapter attached, as RunPod serves it, or the AWQ 4-bit export): the evaluation drafts and a latency benchmark, so the quantised model
is compared with the model it came from on the same decoding (brief items 6 and 7).

    python vm/quant_eval.py --model ~/models/A_qa3_dpo3_awq --name awq --out ~/checkpoints/quant
    python vm/quant_eval.py --model BASE --adapter ~/checkpoints/A_qa3_dpo3/run/adapter --name bf16_lora --out ~/checkpoints/quant

Writes, under --out/<name>/:
  bon_<name>.jsonl           3 drafts per app-format prompt (temperature 0.3, frequency penalty 0.3), as the app asks
  predictions_<name>.jsonl   test_v2 (drafting, extraction, Q&A), greedy, the decoding of vm/predict_qa.py
  latency_<name>.json        batch 1: time to first token, decode tokens per second (p50 / p95 over 20 prompts);
                             batched: output tokens per second over the 89 x 3 drafts; model size on disk
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import trim_repeats  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--name", required=True)
ap.add_argument("--adapter", help="LoRA adapter served on --model (BASE = the course copy of Qwen2.5-7B-Instruct)")
ap.add_argument("--out", required=True)
ap.add_argument("--app", default="trainset/out/test_app.jsonl")
ap.add_argument("--v2", default="trainset/out/test_v2.jsonl")
ap.add_argument("--bench", type=int, default=20)
ap.add_argument("--latency-only", action="store_true", help="skip the drafts; prefix caching off, so first-token times are real prefills")
a = ap.parse_args()

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
model = BASE if a.model == "BASE" else os.path.expanduser(a.model)
lora = LoRARequest(a.name, 1, os.path.expanduser(a.adapter)) if a.adapter else None
out = Path(a.out).expanduser() / a.name
out.mkdir(parents=True, exist_ok=True)
load = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]   # noqa: E731

t0 = time.time()
llm = LLM(model, max_model_len=6144, gpu_memory_utilization=0.9, seed=11, enable_prefix_caching=not a.latency_only,
          **({"enable_lora": True, "max_lora_rank": 64} if lora else {}))
load_s = time.time() - t0
tok = llm.get_tokenizer()
chat = lambda r: tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True)   # noqa: E731

# 1. best of 3 on the app-format prompts
app = load(a.app)
bon_s = bon_tokens = 0
t0 = time.time()
outs = [] if a.latency_only else llm.generate([chat(r) for r in app], SamplingParams(temperature=0.3, frequency_penalty=0.3, max_tokens=2200, n=3, seed=11), lora_request=lora)
bon_s = time.time() - t0
if a.latency_only:
    outs = []
bon_tokens = sum(len(c.token_ids) for o in outs for c in o.outputs)
with open(out / f"bon_{a.name}.jsonl", "a" if a.latency_only else "w", encoding="utf-8") as fh:
    for r, o in zip(app, outs):
        fh.write(json.dumps({"id": r["id"], "candidates": [c.text for c in o.outputs],
                             "finish": [c.finish_reason for c in o.outputs]}, ensure_ascii=False) + "\n")
print(f"{a.name}: best of 3 on {len(app)} prompts, {bon_tokens} tokens in {bon_s:.0f} s", flush=True)

# 2. the full test set, greedy
CAP = {"drafting": 2200, "extraction": 3000, "qa": 600}
v2 = load(a.v2)
params = [SamplingParams(temperature=0, frequency_penalty=0.3 if r["metadata"]["skill"] == "drafting" else 0.0,
                         max_tokens=CAP[r["metadata"]["skill"]]) for r in v2]
outs = [] if a.latency_only else llm.generate([chat(r) for r in v2], params, lora_request=lora)
with open(out / f"predictions_{a.name}.jsonl", "a" if a.latency_only else "w", encoding="utf-8") as fh:
    for r, o in zip(v2, outs):
        raw, finish = o.outputs[0].text, o.outputs[0].finish_reason
        pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
        fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                             "finish": finish, "loop_trimmed": cut}, ensure_ascii=False) + "\n")
print(f"{a.name}: {len(v2)} test_v2 rows", flush=True)

# 3. latency at batch 1: first token (a 1-token request) and decode speed (256 tokens, end-of-text ignored)
bench = [chat(r) for r in app[: a.bench]]
ttft, tps = [], []
llm.generate(bench[:1], SamplingParams(max_tokens=8), lora_request=lora)                      # warm-up
for p in bench:
    t0 = time.perf_counter()
    llm.generate([p], SamplingParams(temperature=0, max_tokens=1), use_tqdm=False, lora_request=lora)
    t1 = time.perf_counter()
    o = llm.generate([p], SamplingParams(temperature=0, max_tokens=256, ignore_eos=True), use_tqdm=False, lora_request=lora)
    t2 = time.perf_counter()
    ttft.append(t1 - t0)
    tps.append((len(o[0].outputs[0].token_ids) - 1) / max(1e-6, (t2 - t1) - (t1 - t0)))


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


size = sum(f.stat().st_size for f in Path(model).glob("*.safetensors")) + (
    sum(f.stat().st_size for f in Path(os.path.expanduser(a.adapter)).glob("*.safetensors")) if a.adapter else 0)
res = {"model": model, "adapter": a.adapter, "name": a.name, "load_seconds": round(load_s, 1), "size_gb": round(size / 1e9, 2),
       "batch1_ttft_s": {"p50": round(statistics.median(ttft), 3), "p95": round(pct(ttft, 0.95), 3)},
       "batch1_decode_tok_s": {"p50": round(statistics.median(tps), 1), "p95_low": round(pct(tps, 0.05), 1)},
       "batched_best_of_3": {"prompts": len(app), "output_tokens": bon_tokens, "seconds": round(bon_s, 1),
                             "tok_s": round(bon_tokens / bon_s, 1)},
       "bench_prompts": len(bench)}
res["prefix_caching"] = not a.latency_only
if a.latency_only:
    res.pop("batched_best_of_3")
json.dump(res, open(out / (f"latency_nocache_{a.name}.json" if a.latency_only else f"latency_{a.name}.json"), "w"), indent=1)
print(json.dumps(res), flush=True)
print("QUANT_EVAL_DONE", flush=True)
