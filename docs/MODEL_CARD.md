# Model card: SME DRHP drafter (A_qa_dpo)

**Status:** research prototype for the capstone (Track A). Drafts are for professional review. Nothing it writes is
filed, signed off or sent without a person checking it against the issuer's documents.

## Model

| | |
|---|---|
| Base | Qwen2.5-7B-Instruct (Apache 2.0) |
| Adaptation | QLoRA, rank 16, alpha 32, all linear layers (run A, 2 epochs, lr 2e-4), then DPO against looping (beta 0.1, lr 1e-5, 223 pairs) |
| Training data | 1,746 rows: 657 drafting, 789 extraction, 300 question answering with guardrails |
| Served as | merged bf16 weights behind an OpenAI-compatible server (vLLM); the app's assistant and drafting call that endpoint |

## Intended use

* Drafting SME DRHP sub-sections (SEBI ICDR Chapter IX, BSE SME) from the issuer's own typed facts.
* Extracting typed facts from issuer passages.
* Answering questions about an issuer's documents, with citations to the passage used.

**Out of scope:** investment advice, predicting listing prices, the main-board regime, pricing and offer terms before
RHP stage (these stay `[●]`), personal identifiers, drafting that omits or softens a mandatory disclosure, and any
filing without a human reviewer.

## Data provenance

* Source documents: public SME offer documents on BSE (2021–2026), used for the test-set companies' sub-sections and
  for training-set companies only. No company appears in both splits (checked by the build).
* Typed facts and answers were written by a teacher model (Qwen3-32B-AWQ, Apache 2.0) and gated: a figure, date or name
  in the output must appear in its source passage; Q&A quotes must be verbatim.
* Issuer input bundles for the end-to-end tests are synthetic, derived from filed documents.
* Personal identifiers in source documents (PAN, Aadhaar, bank details) are masked before training.

## Evaluation (test set: 199 rows from 75 companies, 89 drafting, 50 extraction, 60 Q&A)

| system | grounding (drafting) | invented figures | fact use | Q&A F1 | Q&A cites the answering passage | Q&A guardrails |
|---|---|---|---|---|---|---|
| base model | 0.860 | 19% of drafts | 0.51 | 0.70 | 38% | 38% |
| A_qa_dpo (this model) | 0.799 | 33% of drafts | 0.67 | 0.87 | 100% | 100% |
| with the verifier (masks ungrounded values) | 0.990 | 0% of drafts (0 of 89) | 0.55 | – | – | – |
| teacher, 2-shot (Qwen3-32B) | 0.948 | 6% of drafts | 0.60 | – | – | – |

**Judge (teacher-scored, 1–5, four criteria; 0 parse failures of 445):** the filed text scores 3.94 on average; the
fine-tuned model 3.58; the base model 3.87; the 2-shot base 3.84; agentic RAG with the fine-tuned model 3.55. Read with
care: the judge is the teacher model, which may prefer the base model's style.

**Held-out loss (drafting, extraction):** run A 1.29 / 0.064; base 1.84 / 0.148. Seed spread across three seeds: under
0.01 in loss, larger in generation measures (see TRAINING.md).

Retrieval (agentic RAG over the company's other sections): the answering passage is the top result for 20% of Q&A
questions and within the top five for 37%. With retrieval, Q&A F1 falls to 0.72 and fact use to 0.55, so retrieval is
not used by default.

## Known failure modes

1. **Repetition:** the greedy output loops on some drafts (A_qa_dpo: 19% with the penalty applied; base: 1%). Drafts are
   cut at a loop and flagged `loop_trimmed`.
2. **Invented figures in drafts before verification:** 33% of drafts contain a figure not in their inputs. The verifier
   masks these as `[●]`; without it the output must not be used.
3. **Weaker drafting completeness than the base model** on the teacher-based judge.
4. **Agentic retrieval does not help** in this evaluation; the planner's queries are often too broad.
5. **Mainboard rules** (for example, the 25% public float) are not an SME rule. The model is trained on Chapter IX, but
   it can still mix regimes: check any regulatory statement.

## Refusal and guardrail behaviour

The assistant declines investment advice, personal identifiers, requests to omit or soften a mandatory disclosure, and
requests to fill DRHP-stage offer terms (returns `[●]`). It ignores instructions embedded in issuer documents and says so.
The app also screens these requests by rule before any model call (`rag/guardrails.py`). The red-team results are in
[RED_TEAM_LOG.md](RED_TEAM_LOG.md).

## Limitations

* The test set is 199 rows from 75 companies; intervals are wide (see the evaluation report).
* One teacher produced the training data; its errors are in the training data too.
* The judge is the teacher model, not an independent judge (the plan's gpt-oss-20b did not fit the VM's disk quota).
* Serving was tested as a single merged model on one GPU. Quantised (AWQ) serving is not done.
* The model has not been reviewed by a practising DRHP reviewer on blind comparison; that step needs the project owner.
