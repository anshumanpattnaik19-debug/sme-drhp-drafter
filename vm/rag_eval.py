"""Agentic RAG and baselines on the course VM (one vLLM engine, several systems).

Agent loop (rag_base = base model, rag_A_qa_dpo = the fine-tuned adapter; the same model plans and answers):
  1. plan   the model writes JSON {"queries": [...]} (one or two searches) for the sub-heading or the question
  2. search BM25 over the company's passages (rag/corpus_test.jsonl: the other sections of the same offer document)
  3. answer drafting rows: the row's own prompt (FACTS, outline, sub-heading) plus a numbered RETRIEVED CONTEXT block;
            Q&A rows: the assistant prompt (data.prompts.qa_messages) with the top retrieved passages as EVIDENCE
Leakage control (drafting): a passage is never retrieved if it is the gold unit or shares any 8-word run with the gold
sub-section. Q&A keeps every passage, since its questions are about the document itself.

Also in this job:
  B1  base model, 2-shot (two short train examples of the same kind, same section bucket where possible), drafting and
      extraction rows of test.jsonl
  recall  for Q&A rows: is the answering passage among the retrieved passages (top 1 and top 5 of the first search)

    python vm/rag_eval.py --test trainset/out/test_v2.jsonl --train trainset/out/train_v2.jsonl \
        --corpus rag/corpus_test.jsonl --adapter ~/checkpoints/A_qa-51/adapter --out ~/checkpoints/rag
"""
import argparse
import heapq
import json
import math
import os
import random
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.getcwd())

from transformers import AutoTokenizer  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.lora.request import LoRARequest  # noqa: E402

from data.prompts import evidence_line, qa_messages, trim_repeats  # noqa: E402

BASE = "/storage/tracka/models/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"
CAP = {"drafting": 2200, "extraction": 3000, "qa": 600}
TOP_PER_QUERY = 4
MAX_MODEL_LEN = 10240
MAX_PROMPT = 7000                                  # B1 shots are dropped above this, leaving room for the answer
MAX_CONTEXT = 6
STOP = set("the and for with that this from are was were our its their has have been which into such upon under over also "
           "other any all can may will shall not per".split())
PLAN_SYSTEM = ("You plan document searches for an SME DRHP task. Reply with JSON only: {\"queries\": [\"...\", \"...\"]}. "
               "Give one or two searches of 3 to 8 keywords each, for the issuer's other sections that would give background "
               "for the request.")
RE_FACTS = re.compile(r"^FACTS: (\[.*?\])\s*$", re.M)


def toks(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP]


def grams(s, n=8):
    w = re.findall(r"\w+", s.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


class Index:
    """BM25 over one company's passages (k1 1.2, b 0.75)."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.tf = [Counter(toks(c["text"])) for c in chunks]
        self.dl = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.dl) / max(1, len(self.dl))
        self.df = Counter()
        for t in self.tf:
            self.df.update(t.keys())
        self.n = len(chunks)
        self.grams = [grams(c["text"]) for c in chunks]

    def search(self, query, k, exclude=frozenset()):
        q = set(toks(query))
        scored = []
        for i in range(self.n):
            if i in exclude:
                continue
            s = 0.0
            for t in q:
                f = self.tf[i].get(t)
                if f:
                    idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * self.dl[i] / max(1.0, self.avg)))
            if s > 0:
                scored.append((s, i))
        return [i for _, i in heapq.nlargest(k, scored)]


def read_jsonl(path):
    return [json.loads(line) for line in open(os.path.expanduser(path), encoding="utf-8") if line.strip()]


def user_of(row):
    return row["messages"][1]["content"]


def parse_queries(text, fallback):
    m = re.search(r"\{.*\}", re.sub(r"<think>.*?</think>", "", text or "", flags=re.S), re.S)
    try:
        qs = json.loads(m.group(0)).get("queries") if m else None
    except ValueError:
        qs = None
    qs = [q for q in (qs or []) if isinstance(q, str) and q.strip()][:2]
    return qs or [fallback]


def context_block(chunks):
    lines = [f"[{n}] {c['section'] or 'document'} | {c['heading'][:90]}: {c['text']}" for n, c in enumerate(chunks, 1)]
    return ("RETRIEVED CONTEXT (other sections of the issuer's documents, for background; a figure from it may be used "
            "only where the sub-section needs it, with its [n]):\n" + "\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(os.path.expanduser(a.out))
    out.mkdir(parents=True, exist_ok=True)

    test = read_jsonl(a.test)
    train = read_jsonl(a.train)
    tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)

    # company indexes
    by_doc = defaultdict(list)
    for c in read_jsonl(a.corpus):
        by_doc[c["doc_id"]].append(c)
    index = {d: Index(cs) for d, cs in by_doc.items()}
    print(f"corpus: {sum(len(v) for v in by_doc.values())} passages, {len(index)} companies", flush=True)

    rag_rows = [r for r in test if r["metadata"]["skill"] in ("drafting", "qa")]
    b1_rows = [r for r in test if r["metadata"]["skill"] in ("drafting", "extraction")]

    llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=MAX_MODEL_LEN, gpu_memory_utilization=0.9)
    lora = LoRARequest("adapter", 1, os.path.expanduser(a.adapter))

    def gen(prompts, params, lora_request=None):
        return [o.outputs[0] for o in llm.generate(prompts, params, lora_request=lora_request)]

    # ---------- B1: base model, 2-shot ----------
    pool = defaultdict(list)
    for r in train:
        if r["metadata"]["skill"] in ("drafting", "extraction") and r["metadata"].get("n_tokens_est", 0) <= 1200:
            pool[(r["metadata"]["skill"], r["metadata"].get("section_bucket"))].append(r)
    prompts, params, b1_meta = [], [], []
    for r in b1_rows:
        skill = r["metadata"]["skill"]
        cands = pool.get((skill, r["metadata"].get("section_bucket"))) or pool.get((skill, None)) or \
            [x for k, v in pool.items() if k[0] == skill for x in v]
        shots = random.Random(zlib.crc32(r["id"].encode())).sample(cands, min(2, len(cands)))
        while True:                                   # keep the prompt plus the answer within the context window
            msgs = [r["messages"][0]]
            for s in shots:
                msgs += [s["messages"][1], s["messages"][2]]
            msgs.append(r["messages"][1])
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            if len(tok(text, add_special_tokens=False).input_ids) <= MAX_PROMPT or not shots:
                break
            shots = shots[:-1]
        prompts.append(text)
        params.append(SamplingParams(temperature=0, frequency_penalty=0.3 if skill == "drafting" else 0.0,
                                     max_tokens=CAP[skill]))
        b1_meta.append([s["id"] for s in shots])
    print(f"B1: {len(prompts)} prompts", flush=True)
    res = gen(prompts, params)
    with open(out / "predictions_B1_2shot.jsonl", "w", encoding="utf-8") as fh:
        for r, o, shots in zip(b1_rows, res, b1_meta):
            raw = o.text
            pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
            fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                                 "finish": o.finish_reason, "loop_trimmed": cut, "shots": shots},
                                ensure_ascii=False) + "\n")

    # ---------- agentic RAG: plan, search, answer ----------
    systems = [("rag_base", None), ("rag_A_qa_dpo", lora)]
    recall_rows = []
    for name, lr in systems:
        # 1. plan
        plan_prompts, plan_for = [], []
        for r in rag_rows:
            md = r["metadata"]
            if md["skill"] == "drafting":
                heading = md.get("heading") or ""
                user = (f"COMPANY: {md['company']}\nSECTION: {md.get('section_bucket')}\nSUB-HEADING: {heading}")
                fallback = heading
            else:
                question = user_of(r).split("QUESTION: ")[-1].strip()
                user = f"COMPANY: {md['company']}\nQUESTION: {question}"
                fallback = question
            msgs = [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": user}]
            plan_prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
            plan_for.append(fallback)
        plans = gen(plan_prompts, SamplingParams(temperature=0, max_tokens=120), lora_request=lr)

        # 2. search (leakage-free for drafting)
        contexts, logs = [], []
        for r, plan, fallback in zip(rag_rows, plans, plan_for):
            md = r["metadata"]
            idx = index.get(md["doc_id"])
            queries = parse_queries(plan.text, fallback)
            if idx is None:
                contexts.append([]); logs.append({"id": r["id"], "queries": queries, "hits": []}); continue
            exclude = set()
            if md["skill"] == "drafting":
                gold = grams(r["messages"][-1]["content"])
                for i, g in enumerate(idx.grams):
                    if g & gold or idx.chunks[i]["unit_id"] == md.get("unit_id"):
                        exclude.add(i)
            hits, seen = [], set()
            for q in queries:
                for i in idx.search(q, TOP_PER_QUERY, exclude=exclude):
                    if i not in seen:
                        seen.add(i)
                        hits.append(i)
            hits = hits[:MAX_CONTEXT]
            chunks = [idx.chunks[i] for i in hits]
            contexts.append(chunks)
            logs.append({"id": r["id"], "queries": queries, "hits": [c["chunk_id"] for c in chunks]})
            if md["skill"] == "qa" and name == "rag_base":
                gold_n = md.get("gold_n")
                needle = ""
                if gold_n:
                    for ln in user_of(r).split("\n"):
                        if ln.startswith(f"[{gold_n}] "):
                            needle = re.sub(r"\s+", " ", ln.split(": ", 1)[-1]).lower()[:60]
                norm = [re.sub(r"\s+", " ", c["text"]).lower() for c in chunks]
                first = norm[:1]
                recall_rows.append({"id": r["id"], "top1": any(needle and needle in t for t in first),
                                    "top5": any(needle and needle in t for t in norm)})
        with open(out / f"search_log_{name}.jsonl", "w", encoding="utf-8") as fh:
            for lg in logs:
                fh.write(json.dumps(lg, ensure_ascii=False) + "\n")

        # 3. answer
        ans_prompts, ans_params = [], []
        for r, chunks in zip(rag_rows, contexts):
            md = r["metadata"]
            if md["skill"] == "drafting":
                user = user_of(r).replace("\nDraft the sub-section now.",
                                          ("\n" + context_block(chunks) + "\n\nDraft the sub-section now.") if chunks
                                          else "\nDraft the sub-section now.")
                msgs = [r["messages"][0], {"role": "user", "content": user}]
                ans_params.append(SamplingParams(temperature=0, frequency_penalty=0.3, max_tokens=CAP["drafting"]))
            else:
                question = user_of(r).split("QUESTION: ")[-1].strip()
                lines = [evidence_line(n, "passage", c["section"] or "document", c["heading"][:60], c["text"])
                         for n, c in enumerate(chunks, 1)]
                msgs = qa_messages(md["company"], lines, question)
                ans_params.append(SamplingParams(temperature=0, max_tokens=CAP["qa"]))
            ans_prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
        ans = gen(ans_prompts, ans_params, lora_request=lr)
        with open(out / f"predictions_{name}.jsonl", "w", encoding="utf-8") as fh:
            for r, o in zip(rag_rows, ans):
                raw = o.text
                pred, cut = trim_repeats(raw) if r["metadata"]["skill"] == "drafting" else (raw, False)
                fh.write(json.dumps({"id": r["id"], "metadata": r["metadata"], "prediction": pred, "raw": raw,
                                     "finish": o.finish_reason, "loop_trimmed": cut}, ensure_ascii=False) + "\n")
        print(f"{name}: answered {len(ans)} rows", flush=True)
        if name == "rag_base":
            n = len(recall_rows)
            print(f"recall (Q&A, first plan): top1 {sum(x['top1'] for x in recall_rows) / max(1, n):.3f} "
                  f"top5 {sum(x['top5'] for x in recall_rows) / max(1, n):.3f} over {n} rows", flush=True)

    json.dump({"qa_rows": len(recall_rows), "top1": sum(x["top1"] for x in recall_rows) / max(1, len(recall_rows)),
               "top5": sum(x["top5"] for x in recall_rows) / max(1, len(recall_rows))},
              open(out / "retrieval_recall.json", "w"), indent=1)
    print("RAG_EVAL_DONE", flush=True)


if __name__ == "__main__":
    main()
