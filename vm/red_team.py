"""Red-team run for the fine-tuned Q&A model (20 adversarial prompts, evaluate/red_team_prompts.json) on the course VM.

Each prompt is asked in the assistant's own format (data.prompts.qa_messages) with five passages of one test company as
EVIDENCE. For prompts that carry an injected instruction, that instruction is placed inside one passage.
The answers are written for review; the automatic check is a first pass only (refusal or placeholder markers) and the
log records the reviewer's judgement separately.

    python vm/red_team.py --prompts evaluate/red_team_prompts.json --corpus rag/corpus_test.jsonl \
        --adapter ~/checkpoints/A_qa_dpo/run/adapter --out ~/sme/eval/red_team.jsonl
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())

from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import evidence_line, qa_messages  # noqa: E402

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"

ap = argparse.ArgumentParser()
ap.add_argument("--prompts", required=True)
ap.add_argument("--corpus", required=True)
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

prompts_in = json.load(open(os.path.expanduser(a.prompts), encoding="utf-8"))
chunks = [json.loads(l) for l in open(os.path.expanduser(a.corpus), encoding="utf-8") if l.strip()]
doc = next(c["doc_id"] for c in chunks)
company = next(c["company"] for c in chunks if c["doc_id"] == doc)
passages = random.Random(7).sample([c for c in chunks if c["doc_id"] == doc], 5)

tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
texts = []
for p in prompts_in:
    items = [(c["section"] or "document", c["heading"][:60], c["text"]) for c in passages]
    if p.get("inject"):
        s, h, t = items[2]
        items[2] = (s, h, t + " " + p["inject"])
    lines = [evidence_line(n, "passage", s, h, t) for n, (s, h, t) in enumerate(items, 1)]
    msgs = qa_messages(company, lines, p["question"])
    texts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))

llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=6144, gpu_memory_utilization=0.9)
outs = llm.generate(texts, SamplingParams(temperature=0, max_tokens=600),
                    lora_request=LoRARequest("A_qa_dpo", 1, os.path.expanduser(a.adapter)))
os.makedirs(os.path.dirname(os.path.expanduser(a.out)), exist_ok=True)
with open(os.path.expanduser(a.out), "w", encoding="utf-8") as fh:
    for p, o in zip(prompts_in, outs):
        fh.write(json.dumps({**p, "company": company, "answer": o.outputs[0].text, "finish": o.outputs[0].finish_reason},
                            ensure_ascii=False) + "\n")
print("RED_TEAM_DONE", len(prompts_in), flush=True)
