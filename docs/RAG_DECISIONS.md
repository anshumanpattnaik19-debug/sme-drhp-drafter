# Retrieval (RAG): documented decisions and the required comparison

Measured on the course VM on 20 Nov 2026 (`vm/retrieval_eval.py`, `vm/rag_gen.py`, job `rag2`); scored locally with
`evaluate/metrics.py`. Corpus: `rag/corpus_test.jsonl`, the **761 sections** (14,295 sub-heading units, 38,947 passages) of the
offer documents of the 75 test companies. A query searches only its own company's sections (tenant isolation, as in the app).

## 1. Chunking

Passages of about 110 words, split at sentence ends with a one-sentence overlap; tables become chunks of caption + header +
up to 8 rows, so a row is always read with its column names (`rag/index.py`). Sub-heading boundaries are kept: a passage never
spans two sub-sections. Chosen because DRHP answers are a sentence or a table row, and a 110-word passage fits six evidence items
in the assistant's prompt. Not compared against other sizes on this corpus (a limitation).

## 2. Embedding model and retriever

Q&A rows with a gold passage (38 of the 60), query = the question:

| Retriever | Recall@1 | Recall@5 | MRR@10 |
|---|---|---|---|
| BM25 (k1 1.2, b 0.75) | 0.658 | 0.789 | 0.722 |
| BAAI/bge-m3 dense | 0.474 | 0.737 | 0.588 |
| hybrid (reciprocal rank fusion, k 60) | 0.553 | 0.763 | 0.670 |
| **BM25 + bge-reranker-v2-m3** | **0.684** | **0.895** | **0.766** |
| hybrid + bge-reranker-v2-m3 | 0.658 | 0.895 | 0.753 |

Decision: **BM25 first stage, cross-encoder reranker over its top 30.** Dense retrieval alone is worse than BM25 on these
documents (exact figures, names, section words matter more than paraphrase), and fusing it in does not beat BM25 + reranker.
The app keeps BM25 by default (the pod is a CPU machine; the reranker is 568M parameters) and runs the reranker when
`DRHP_RERANK_MODEL` names it (`rag/index.py`, tested in `tests/test_rerank.py`). The earlier agentic setting (the model writes
its own search queries) found the gold passage in the top 5 for only 37% of questions; querying with the question itself and
reranking gives 89%.

## 3. The required comparison (149 rows: 89 drafting, 60 Q&A)

| System | Q&A F1 | Q&A cites gold | Guardrails | Draft grounding | Drafts w/ invented figure | Fact use |
|---|---|---|---|---|---|---|
| base | 0.695 | 38% | 38% | 0.860 | 19.1% | 0.505 |
| base + RAG | 0.602 | 15% | 38% | 0.666 | 40.4% | 0.461 |
| fine-tuned | **0.876** | **100%** | **100%** | **0.951** | **11.2%** | **0.630** |
| fine-tuned + RAG | 0.785 | 18% | 88% | 0.764 | 22.5% | 0.596 |

Paired, by company bootstrap: fine-tuned + RAG against base + RAG: Q&A F1 +0.18 (+0.11 to +0.26), invented-figure drafts
−18 points (−29 to −6), fact use +0.14. Fine-tuned + RAG against fine-tuned: Q&A F1 −0.09 (−0.15 to −0.04), invented-figure
drafts +11 points (+1 to +22).

**Reading it.** Fine-tuning helps with or without retrieval. Retrieval does not help this task as measured: (a) without RAG the
Q&A rows are given the answering passage; with RAG it must be found (recall@5 0.89), so part of the drop is retrieval misses;
(b) for drafting, a figure taken from retrieved context counts as not grounded, because a sub-section must be drafted from its
own facts; the measure is strict by design. So the app uses retrieval for the assistant's search over the issuer's own files
(where nothing else supplies the evidence) and not as extra context for drafting.

## 4. Limits

38 Q&A rows with a gold passage; one corpus of 75 companies; chunk size not varied; the reranker's latency on the CPU pod not
measured.
