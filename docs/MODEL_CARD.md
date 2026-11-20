# Model card: SME DRHP drafter (A_qa3_dpo3)

**Status:** research prototype for the capstone (Track A). Drafts are for professional review. Nothing it writes is
filed, signed off or sent without a person checking it against the issuer's documents.

## Model

| | |
|---|---|
| Base | Qwen2.5-7B-Instruct (Apache 2.0) |
| Adaptation | QLoRA, rank 16, alpha 32, all linear layers (run A's settings, 2 epochs, lr 2e-4) on train_v3 with 306 abstention variants, then DPO on 890 on-policy pairs ranked by the app's guard and fact use (beta 0.1, lr 5e-6, 2 epochs) |
| Training data | 2,052 rows: 963 drafting (306 abstention variants), 789 extraction, 300 question answering with guardrails |
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
| A_qa_dpo (previous model) | 0.799 | 33% of drafts | 0.67 | 0.87 | 100% | 100% |
| **A_qa3_dpo3 (this model)**, single draft, full test | 0.951 | 11.2% of drafts | 0.63 | 0.88 | 100% | 100% |
| teacher, 2-shot (Qwen3-32B) | 0.948 | 6% of drafts | 0.60 | – | – | – |

**Drafts as the app makes them** (89 app-format prompts: unknown facts as `[●]`, no precedent; 3 drafts per request, guarded,
the best kept with a length floor; 20 Nov 2026):

| system | invented figure after the guard | values masked per draft | fact use | loops |
|---|---|---|---|---|
| base model | 0% (0 of 89) | 0.65 | 0.54 | 1.1% |
| A_qa_dpo (previous) | 6.7% (6 of 89) | 2.29 | 0.65 | 0% |
| **A_qa3_dpo3 (this model)** | 0% (0 of 89) | 0.61 | 0.70 | 0% |

This model ties the base on invented figures (0 against 0 of 89; two near-zero rates cannot be told apart on 89 drafts) and is better on fact use, masked values, Q&A (0.88 against 0.70, guardrails 100% against 38%) and extraction (F1 0.59 against 0.36). The numbers use the guard and metric of the evening of 20 Nov: before them this model read 1 of 89 flagged (a grounded figure printed with spaces) and the previous adapter 7 of 89. The repair closes spaced digits only when a fact has the same digits, and the metric skips serial numbers in a numbered run and the split plural "Regulation s 17, 18"; it was changed after the results were seen, applies to every model, and is tested in `tests/test_serials_and_spacing.py`. Earlier versions of this card reported 0 of 89 (not reproduced, item 25) and 3 of 89 for the previous model (a selection that favoured short drafts; corrected). Details: `FAILURE_LOG.md` item 34, `RETRAINING_LOG.md` run 14.
A second run of the same prompts on the deployed endpoint (fresh samples) gave 0 of 89 flagged, 0.46 masked, fact use 0.66, 0 loops. Test set note: 89 drafts from 75 companies; extraction F1 on 50 rows.

**Judge (teacher-scored, 1–5, four criteria; 0 parse failures of 445):** the filed text scores 3.94 on average; the
fine-tuned model 3.58; the base model 3.87; the 2-shot base 3.84; agentic RAG with the fine-tuned model 3.55. Read with
care: the judge is the teacher model, which may prefer the base model's style.

**Held-out loss (drafting, extraction):** run A 1.29 / 0.064; base 1.84 / 0.148. Seed spread across three seeds: under
0.01 in loss, larger in generation measures (see TRAINING.md).

Retrieval (agentic RAG over the company's other sections): the answering passage is the top result for 20% of Q&A
questions and within the top five for 37%. With retrieval, Q&A F1 falls to 0.72 and fact use to 0.55, so retrieval is
not used by default.

## Known failure modes

1. **Repetition:** the greedy output loops on some drafts (A_qa3_dpo3: 8% of single drafts with the penalty applied; previous adapter 19%; base 1%). Drafts are
   cut at a loop and flagged `loop_trimmed`.
2. **Invented figures in drafts before verification:** 11% of single drafts (previous adapter 33%) contain a figure not in their inputs. The verifier
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

A Responsible AI layer (`rai/`, [RESPONSIBLE_AI.md](../RESPONSIBLE_AI.md)) adds input and output checks around the model
(jailbreak, prompt extraction, data exfiltration, securities fraud, personal identifiers, unsupported claims, bias language),
a hash-chained audit log with incident escalation, and an evaluation against the base model
([RAI_EVAL_REPORT.md](RAI_EVAL_REPORT.md), 20 Nov 2026). Fine-tuning improved refusals of harmful and policy-breaking
requests (harmful compliance 62% to 0% on 8 probes, guardrail rows 38% to 100%). Three regressions were found: false
"instruction ignored" notices in 13% of probe answers (removed by the layer), unequal answers across name-coded identities in
2 of 9 counterfactual cases (open), and lower figure overlap between the three app drafts. None of this is a certification.

## Limitations

* The test set is 199 rows from 75 companies; intervals are wide (see the evaluation report).
* One teacher produced the training data; its errors are in the training data too.
* The judge is the teacher model, not an independent judge (the plan's gpt-oss-20b did not fit the VM's disk quota).
* Serving runs the adapter on the bf16 base (RunPod). An AWQ 4-bit export was evaluated on the course VM (5.6 GB, about 3x faster decoding, Q&A F1 0.853 against 0.876) and is not served in production.
* The model has not been reviewed by a practising DRHP reviewer on blind comparison; that step needs the project owner.
