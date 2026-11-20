"""The brief's required comparison with the retriever chosen by vm/retrieval_eval.py: base + RAG and fine-tuned + RAG on the
drafting and Q&A rows of test_v2 (the no-retrieval predictions of both already exist). Prompts as in vm/rag_eval.py: drafting rows
get a numbered RETRIEVED CONTEXT block before "Draft the sub-section now."; Q&A rows answer from the retrieved passages as EVIDENCE.

    python vm/rag_gen.py --contexts ~/checkpoints/rag2/contexts_hybrid_rerank.jsonl --adapter ~/checkpoints/A_qa3_dpo3/run/adapter \
        --name A_qa3_dpo3 --out ~/checkpoints/rag2
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import evidence_line, qa_messages, trim_repeats  # noqa: E402

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
CAP = {"drafting": 2200, "qa": 600}


def context_block(chunks):
    lines = [f"[{n}] {c['section'] or 'document'} | {c['heading'][:90]}: {c['text']}" for n, c in enumerate(chunks, 1)]
    return ("RETRIEVED CONTEXT (other sections of the issuer's documents, for background; a figure from it may be used "
            "only where the sub-section needs it, with its [n]):\n" + "\n".join(lines))


ap = argparse.ArgumentParser()
ap.add_argument("--test", default="trainset/out/test_v2.jsonl")
ap.add_argument("--contexts", required=True)
ap.add_argument("--adapter", required=True)
ap.add_argument("--name", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
out = Path(os.path.expanduser(a.out))
out.mkdir(parents=True, exist_ok=True)

ctx = {}
for l in open(os.path.expanduser(a.contexts), encoding="utf-8"):
    x = json.loads(l)
    ctx[x["id"]] = x["chunks"]
rows = [r for r in (json.loads(l) for l in open(a.test, encoding="utf-8") if l.strip()) if r["metadata"]["skill"] in CAP]

llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=10240, gpu_memory_utilization=0.9, seed=11)
tok = llm.get_tokenizer()
prompts, params = [], []
for r in rows:
    md, chunks = r["metadata"], ctx.get(r["id"], [])
    if md["skill"] == "drafting":
        user = r["messages"][1]["content"]
        if chunks:
            user = user.replace("\nDraft the sub-section now.", "\n" + context_block(chunks) + "\n\nDraft the sub-section now.")
        msgs = [r["messages"][0], {"role": "user", "content": user}]
        params.append(SamplingParams(temperature=0, frequency_penalty=0.3, max_tokens=CAP["drafting"]))
    else:
        question = r["messages"][1]["content"].split("QUESTION: ")[-1].strip()
        lines = [evidence_line(n, "passage", c["section"] or "document", c["heading"][:60], c["text"]) for n, c in enumerate(chunks, 1)]
        msgs = qa_messages(md["company"], lines, question)
        params.append(SamplingParams(temperature=0, max_tokens=CAP["qa"]))
    prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))

for name, lora in (("base", None), (a.name, LoRARequest(a.name, 1, os.path.expanduser(a.adapter)))):
    outs = llm.generate(prompts, params, lora_request=lora)
    with open(out / f"predictions_rag2_{name}.jsonl", "w", encoding="utf-8") as fh:
        for r, o in zip(rows, outs):
            raw = o.outputs[0].text
            pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
            fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                                 "finish": o.outputs[0].finish_reason, "loop_trimmed": cut}, ensure_ascii=False) + "\n")
    print(f"rag2 {name}: {len(rows)} rows", flush=True)
print("RAG_GEN_DONE", flush=True)
