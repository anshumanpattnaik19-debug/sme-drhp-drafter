"""Retrieval choices measured, not assumed (brief item 5: chunking, embedding model and a reranking step, each a documented
decision). Corpus: rag/corpus_test.jsonl, the 761 sections (14,295 sub-heading units, 38,947 passages of about 110 words) of the
75 test companies' offer documents; a query searches only its own company's sections.

Q&A rows with a gold passage (the question's own answer): query = the question. Recall@1, recall@5 and MRR@10 of the gold
passage for each retriever:
  bm25          BM25 (k1 1.2, b 0.75) over the passage text
  dense         BAAI/bge-m3 embeddings, cosine
  hybrid        reciprocal rank fusion (k 60) of the top 50 of each
  bm25+rerank   BAAI/bge-reranker-v2-m3 cross-encoder over the BM25 top 30
  hybrid+rerank the same over the hybrid top 30

It also writes the top passages of every retriever for the drafting and Q&A rows (contexts_<name>.jsonl), with the leakage
control of vm/rag_eval.py for drafting (no passage of the gold unit, none sharing an 8-word run with the gold sub-section), so the
generation step (vm/rag_gen.py) reuses them. Models load from HF_HOME (set it outside the 35 GB home quota).

    python vm/retrieval_eval.py --test trainset/out/test_v2.jsonl --corpus rag/corpus_test.jsonl --out ~/checkpoints/rag2
"""
import argparse
import heapq
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

STOP = set("the and for with that this from are was were our its their has have been which into such upon under over also "
           "other any all can may will shall not per what when how who".split())
K_CTX = 6


def toks(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP]


def grams(s, n=8):
    w = re.findall(r"\w+", s.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


class BM25:
    def __init__(self, texts):
        self.tf = [Counter(toks(t)) for t in texts]
        self.dl = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.dl) / max(1, len(self.dl))
        self.df = Counter()
        for t in self.tf:
            self.df.update(t.keys())
        self.n = len(texts)

    def rank(self, query, k, exclude=frozenset()):
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


def rrf(lists, k=60):
    score = defaultdict(float)
    for lst in lists:
        for r, x in enumerate(lst):
            score[x] += 1 / (k + r)
    return sorted(score, key=lambda x: -score[x])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--embed", default="BAAI/bge-m3")
    ap.add_argument("--rerank", default="BAAI/bge-reranker-v2-m3")
    a = ap.parse_args()
    out = Path(os.path.expanduser(a.out))
    out.mkdir(parents=True, exist_ok=True)
    from sentence_transformers import CrossEncoder, SentenceTransformer

    test = [json.loads(l) for l in open(a.test, encoding="utf-8") if l.strip()]
    by_doc = defaultdict(list)
    for l in open(a.corpus, encoding="utf-8"):
        c = json.loads(l)
        by_doc[c["doc_id"]].append(c)
    n_sections = len({(c["doc_id"], c["section"]) for cs in by_doc.values() for c in cs})
    print(f"corpus: {sum(len(v) for v in by_doc.values())} passages, {n_sections} sections, {len(by_doc)} companies", flush=True)

    emb_model = SentenceTransformer(a.embed, device="cuda")
    emb_model.max_seq_length = 512
    bm, emb = {}, {}
    for d, cs in by_doc.items():
        texts = [f"{c['section']} {c['heading']} {c['text']}" for c in cs]
        bm[d] = BM25(texts)
        emb[d] = emb_model.encode(texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
    print("indexes built", flush=True)
    reranker = CrossEncoder(a.rerank, device="cuda", max_length=512)

    rows = [r for r in test if r["metadata"]["skill"] in ("drafting", "qa")]
    methods = ["bm25", "dense", "hybrid", "bm25+rerank", "hybrid+rerank"]
    contexts = {m: {} for m in methods}
    recall = {m: [] for m in methods}
    for r in rows:
        md = r["metadata"]
        d = md["doc_id"]
        if d not in by_doc:
            continue
        cs = by_doc[d]
        if md["skill"] == "drafting":
            query = f"{md.get('section_bucket') or ''} {md.get('heading') or ''}".strip()
            gold = grams(r["messages"][-1]["content"])
            exclude = {i for i, c in enumerate(cs) if c["unit_id"] == md.get("unit_id") or grams(c["text"]) & gold}
        else:
            query = r["messages"][1]["content"].split("QUESTION: ")[-1].strip()
            exclude = set()
        b = bm[d].rank(query, 50, exclude)
        qv = emb_model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = emb[d] @ qv
        dn = [int(i) for i in np.argsort(-sims) if int(i) not in exclude][:50]
        hy = rrf([b, dn])
        ranked = {"bm25": b, "dense": dn, "hybrid": hy}
        for name, base in (("bm25+rerank", b), ("hybrid+rerank", hy)):
            head = base[:30]
            if head:
                sc = reranker.predict([(query, f"{cs[i]['section']} {cs[i]['heading']} {cs[i]['text']}") for i in head],
                                      batch_size=32, show_progress_bar=False)
                head = [i for _, i in sorted(zip(sc, head), key=lambda x: -float(x[0]))]
            ranked[name] = head + base[30:]
        for m in methods:
            contexts[m][r["id"]] = [cs[i] for i in ranked[m][:K_CTX]]
        if md["skill"] == "qa" and md.get("gold_n"):
            needle = ""
            for ln in r["messages"][1]["content"].split("\n"):
                if ln.startswith(f"[{md['gold_n']}] "):
                    needle = re.sub(r"\s+", " ", ln.split(": ", 1)[-1]).lower()[:60]
            if not needle:
                continue
            for m in methods:
                norm = [re.sub(r"\s+", " ", cs[i]["text"]).lower() for i in ranked[m][:10]]
                pos = next((p for p, t in enumerate(norm) if needle in t), None)
                recall[m].append(pos)

    res = {"corpus": {"passages": sum(len(v) for v in by_doc.values()), "sections": n_sections, "companies": len(by_doc)},
           "embed": a.embed, "rerank": a.rerank, "qa_rows_with_gold": len(recall["bm25"]), "methods": {}}
    for m in methods:
        ps = recall[m]
        n = max(1, len(ps))
        res["methods"][m] = {"recall@1": round(sum(p == 0 for p in ps) / n, 3),
                             "recall@5": round(sum(p is not None and p < 5 for p in ps) / n, 3),
                             "mrr@10": round(sum(1 / (p + 1) for p in ps if p is not None) / n, 3)}
        with open(out / f"contexts_{m.replace('+', '_')}.jsonl", "w", encoding="utf-8") as fh:
            for rid, chunks in contexts[m].items():
                fh.write(json.dumps({"id": rid, "chunks": chunks}, ensure_ascii=False) + "\n")
    json.dump(res, open(out / "retrieval_eval.json", "w"), indent=1)
    print(json.dumps(res, indent=1), flush=True)
    del emb_model, reranker
    torch.cuda.empty_cache()
    print("RETRIEVAL_DONE", flush=True)


if __name__ == "__main__":
    main()
