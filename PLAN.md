# sme_drhp_drafter: project plan (v2)

Plan v2 of 2026-10-31, revised after a review that scored v1 67/100. **Nothing in this folder is built yet.**

Capstone Track A (model-side): a fine-tuned 7–8B open-weight model that drafts an **SME DRHP**
(SEBI ICDR Chapter IX, BSE SME / NSE Emerge) from the issuer's own files: PDF, Word, Excel, scanned PDF, images.
This replaces the pitchbook and data-room datasets as the main project; those stay as optional extras.

| decision | value |
|---|---|
| board | SME only |
| inputs | PDF, Word, Excel, scanned PDF, images |
| builder | Claude Code writes and tests all code on the laptop (no GPU); GPU steps run as Colab notebooks |
| GPU | **Colab Pro** (A100 for the teacher and quantisation, L4 for training and evaluation) |
| human reviewer | **the project owner (has worked on DRHPs)**; time needed is listed in section 9 |
| teacher | open-weight, chosen in Week 0 between Qwen3-32B and Qwen3-30B-A3B |
| student | Qwen2.5-7B-Instruct |

What changed from v1: drafting by real sub-heading instead of token chunks; training the model to pick facts
(distractor facts); facts as typed values; template and teacher baselines; near-duplicate leakage control;
5 core sections × 30 test rows with confidence intervals and 3 seeds; judge checked against the reviewer;
success criteria fixed in advance; 5 issuer input bundles; offline tests and a mock model server; GPU load cut.

---

## 1. What the system produces

Input: a folder of issuer files (restated financials, auditor's report, MoA/AoA, board and shareholder
resolutions, allotment history, promoter and director details, KMP CVs, litigation list from counsel,
licences and approvals, material contracts, commissioned industry report, project-cost quotations, board-approved
offer terms).

Output: a DRHP-stage draft `.docx` in SME section order, where

* every figure and name links back to the input file and page it came from;
* anything the inputs do not support is left as `[●]` with a "missing input" note, never guessed;
* a review pack lists missing inputs, cross-section mismatches and checklist gaps.

It is a **first draft for the lead manager and legal counsel**, not a filing-ready document. Out of scope: the
restated financial statements and auditor's report (inserted as provided), legal opinions, the industry report
itself, valuation advice, price setting.

## 2. What the data gives us (measured 2026-10-31 from `ipo_prospectus_sft/chunks`)

| | value |
|---|---|
| SME offer documents | 455 (train 354, test 101; split by company, inherited) |
| document types | 448 final prospectuses, 7 DRHPs |
| listing years | 2021: 5, 2022: 52, 2023: 61, 2024: 66, 2025: 151, 2026: 120 |
| size per document | median 270k Qwen tokens (p10 193k, p90 350k) |
| section labels | risk factors 99%, our business 99%, objects 98%, management 98%, promoters 99%, history 77% |

Consequences:

* **Targets are final prospectuses, not DRHPs.** Price, issue size in rupees, dates, lot size, market-maker and
  allotment details are masked to `[●]` in training targets so the model learns DRHP-stage drafting.
* **A document is ~270k tokens,** so the model drafts one sub-section at a time and code assembles the document.

## 3. Who writes each section

| writer | sections | share of an SME document |
|---|---|---|
| **Inserted as provided** | restated financial statements, auditor's report, statement of tax benefits | ~12% |
| **Code** (parsed inputs; rules only from the official ICDR text, flagged VERIFY) | capital structure tables, capitalisation statement, summary financial information, basis for offer price ratios, offer structure and allocation, other financial information, financial indebtedness table, the offer | ~11% |
| **Templates** (nearest train-split precedent, fields filled from the fact store) | definitions, conventions, forward-looking statements, general information, offer procedure, terms of the offer, restrictions on foreign ownership, other regulatory disclosures, articles of association, material contracts list, declaration, key regulations, dividend policy | ~40% |
| **SLM, core (evaluated)** | risk factors, our business, objects of the offer, our management, promoters + history and corporate matters | ~20% |
| **SLM, extended (drafted, reported qualitatively)** | industry overview, MD&A, outstanding litigation, government approvals, summary of the offer document | ~17% |

Headline metrics are on the 5 core sections only, so each has enough test rows (section 7).

## 4. Pipeline

```
issuer files ──► 1 ingest ──► 2 classify ──► 3 extract typed facts ──► fact store (type, label, value, unit, period, file, page)
                                                                            │
          4 plan: SME section outline with real sub-headings ◄──────────────┤
                                                                            │
          5 route facts to each sub-section (same router as in training) ◄──┘
                                    │
      ┌─────────────────┬───────────┼──────────────┬──────────────────────────────┐
      ▼                 ▼           ▼              ▼                              ▼
  insert files      code tables   templates   SLM drafts sub-section k from: outline, routed facts,
                                              summary of sub-section k-1, 1 retrieved precedent
      └─────────────────┴───────────┼──────────────┴──────────────────────────────┘
                                    ▼
          6 verify: grounding, cross-section consistency, disclosure checklist, no price/date at DRHP stage
                                    ▼
          7 assemble .docx (drhp_template/lib.js styling) + review pack
```

1. **Ingest.** Digital PDF and Word with docling (keeps tables); Excel with openpyxl/pandas; scanned PDF and
   images with PaddleOCR, and Qwen2.5-VL-7B for tables in images. Every block keeps file, page and position.
2. **Classify** each file with keyword rules first, the SLM as fallback.
3. **Extract typed facts** with the fine-tuned SLM (skill 1). Excel financials are parsed by code.
4. **Plan.** The outline of each core section uses the sub-headings that appear in ≥ 60% of train-split SME
   documents for that section, plus the issuer-specific ones the facts call for (e.g. one risk factor per
   material litigation item).
5. **Route facts.** BM25 over the fact store with the sub-heading and section as the query, top 40 facts.
   **The same router builds the training inputs** (section 5), so training and inference see the same kind of input.
6. **Verify.** Every number and proper name in a draft is in the fact store; the same figure matches across
   summary, risk factors, objects and MD&A; mandatory items per section are present; no price or date that a
   DRHP would not have.
7. **Assemble** with the docx-js styling in `drhp_template/lib.js`; fact citations become comments.

## 5. Training data

### 5.1 Unit: a real sub-section

A segmenter splits each core section into the sub-sections under its real headings (risk factors: one numbered
risk factor or a run of up to 4 short ones). Units of 150–1,500 tokens; longer ones are split at paragraph
boundaries and flagged `continuation`, shorter ones merged with the next. Each unit carries its section outline
and a 2-sentence summary of the unit before it (written by the teacher), which the student also receives at
inference.

### 5.2 Facts as typed values

The teacher extracts the facts the unit was built from as typed records:
`{type: amount|percent|date|count|person|entity|place|short_text, label, value, unit, period}`.
`short_text` is limited to 12 words. Any fact sharing an 8-word sequence with the target text is rewritten or
dropped, so the source wording cannot leak into the input.

### 5.3 Gates (code)

| gate | rule | why |
|---|---|---|
| precision | every fact value occurs in the source unit | no invented inputs |
| coverage | every number and ≥ 90% of proper names in the target occur in the facts | a fact the teacher misses would teach the student to invent |
| leakage | n-gram overlap between facts and target below threshold (5.2) | the model must write, not copy |

Target cleaning: rejoin broken words, drop page headers and footers, skip units that are mostly flattened
tables, apply the DRHP-stage `[●]` masking.

### 5.4 Fact selection: distractors

The training input is what the router (step 5 of the pipeline) returns for the unit's sub-heading from **all**
of the company's facts: the unit's own facts plus facts from other units of the same company. About half of the
facts in an input are not used by the target. The model learns to pick the relevant facts and ignore the rest,
which is what it has to do at inference. Ablation 1 removes the distractors to measure this.

### 5.5 Two skills, one model (Track A ceiling: 2,000 examples)

| skill | input → output | train | test |
|---|---|---|---|
| **1. Extraction** | raw text of a section or file (30% rendered and re-read by OCR) → typed facts JSON | 800 | 50 |
| **2. Drafting, core** | outline, sub-heading, routed facts, previous summary (+ precedent in half the rows) → sub-section text | 750 (150 per core section) | **150 (30 per core section)** |
| **2. Drafting, extended** | same | 250 (50 per extended section) | 0 (qualitative only) |
| total | | **1,800** | **200** |

At most 6 rows per company; weighted towards 2025–2026 listings because SME rules were tightened in 2025
(confirm the exact changes from the official SEBI circulars). Test rows come from at least 60 different test
companies. Row budget: system ~200 + facts ≤ 1,500 + outline and summary ≤ 300 + precedent ≤ 2,000 +
target ≤ 1,600 tokens → `max_seq_len` 6,144.

### 5.6 Leakage control

Many SME issues share lead managers and law firms, so near-identical boilerplate appears in both splits.
MinHash (5-word shingles) flags every test unit with Jaccard ≥ 0.6 to any train unit. All metrics are reported
on the full test set **and** on the novel subset (no near-duplicate). The share of near-duplicates per section is
reported as a finding in its own right.

## 6. RAG layer

* **Corpus.** Train-split SME sub-sections only (never test companies) as precedents, plus the official ICDR
  Chapter IX text and SME circulars downloaded from SEBI. One document per company-section, sampled to 1,000.
* **Chunking** (documented decision): sub-heading units (5.1) vs fixed 600-token windows.
* **Embeddings:** BAAI/bge-m3 vs BM25; hybrid with reciprocal rank fusion (`ipo_pitch_dataset/rag/retrieve.py`).
* **Reranker:** bge-reranker-v2-m3.
* **Retrieval metric, separate from drafting quality:** recall@k of a same-sub-heading precedent from the same
  sector, and the router's recall of the gold facts (5.4).

## 7. Evaluation

### 7.1 Systems compared (same 200 test rows)

| id | system | role |
|---|---|---|
| B0 | Qwen2.5-7B-Instruct, zero-shot | baseline (Week 1 gate) |
| B1 | Qwen2.5-7B-Instruct, 2-shot | baseline (Week 1 gate) |
| B2 | **template**: nearest train precedent for the same sub-heading, facts substituted by code | is fine-tuning worth it over boilerplate? |
| B3 | teacher, 2-shot | ceiling |
| R0 | base + RAG | required comparison |
| F1 | fine-tuned | required comparison |
| F2 | fine-tuned + RAG | the system |

### 7.2 Metrics

| metric | how |
|---|---|
| grounding (precision) | share of numbers and names in the draft that are in the input facts |
| invented-figure rate | share of drafts with at least one number not in the input facts |
| fact use (recall) | share of the gold facts that appear in the draft (distractors excluded) |
| distractor leakage | share of drafts that use a distractor fact |
| checklist coverage | mandatory items per section present (list fixed in Week 0 by the reviewer) |
| similarity to the filed text | ROUGE-L and BERTScore, full and novel subsets |
| extraction | field-level F1 and JSON validity on the 50 extraction rows |
| LLM judge | gpt-oss-20b (different family from the teacher); rubric: completeness, regulatory tone, no invention, structure |
| speed | latency and tokens/s per sub-section and for a whole draft on the vLLM endpoint |
| end to end | 5 issuer bundles (section 7.5) |

### 7.3 Statistics

* 95% confidence intervals by bootstrap over companies (1,000 resamples), per section and overall.
* F2 vs R0 and F2 vs B2 by paired bootstrap on the same rows.
* The best configuration is trained with 3 seeds; mean and spread are reported.

### 7.4 Success criteria (fixed now, before the dataset freeze)

| id | criterion |
|---|---|
| H1 | F2 grounding ≥ 0.98, and above R0 with non-overlapping 95% intervals |
| H2 | F2 invented-figure rate ≤ 2% of drafts |
| H3 | F2 checklist coverage ≥ B2 + 10 points |
| H4 | F2 beats B2 on the judge score (paired bootstrap, p < 0.05) and in the reviewer's blind comparison |
| H5 | on the 5 bundles, 0 invented figures and ≥ 90% of draft facts traced to a bundle file |

If a criterion fails it is reported as failed; thresholds are not moved after the freeze.

### 7.5 Issuer bundles (the real task)

Five held-out test companies. Claude Code rebuilds the files an issuer would hand over from each company's
filed document: Excel financials, Word board and shareholder resolutions, Word CVs, a litigation list, the MoA as
PDF, one scanned certificate (rendered, skewed, noised) and one table as an image. The full pipeline runs from
the bundle to `.docx`, and the draft is compared with the filed document. Limitation: the bundles are derived from
the filed document, so they test formats and the pipeline, not missing or contradictory issuer data; the reviewer
adds 2 deliberately missing and 1 contradictory item per bundle to test `[●]` and the consistency check.
Client files from the reviewer's past DRHP work are not used unless their use is permitted.

### 7.6 Judge check and human review (the reviewer)

* The reviewer scores 50 drafts on the judge rubric without seeing the judge's scores; weighted kappa between
  reviewer and judge is reported. Below 0.6, the judge is reported as secondary only.
* Blind comparison: for 5 core sections × 5 companies, the reviewer sees F2, B2 and the filed text in random order,
  unlabelled, and ranks them.

### 7.7 Fine-tuning runs (Weights & Biases)

| run | config | purpose |
|---|---|---|
| A | r16, lr 2e-4, all linear layers, 2 epochs | required run 1 |
| B | r64, lr 1e-4 | required run 2 |
| Ablation 1 | best of A/B without distractor facts | does fact-selection training matter? |
| Seeds | best of A/B, 2 more seeds | variance |
| DPO (stretch) | 250 pairs: verified draft vs the same draft with an unsupported figure, a changed fact or a dropped mandatory item | only if compute allows after the seeds |

## 8. Serving and responsible AI (Week 4)

* Merge the best adapter, AWQ 4-bit, vLLM behind FastAPI, Docker Compose (pattern in `ipo_pitch_dataset/serve/`).
  Endpoints: `/ingest`, `/facts`, `/draft/section`, `/draft/full` (background job), `/review`.
* Model card: intended use (first draft for professionals), data provenance (public BSE filings 2021–2026),
  measured failure modes, refusals.
* Red-team log, 20 prompts: instructions hidden in uploaded files ("state the company has no litigation"),
  requests to fill missing figures, to soften risk factors or to drop a litigation item, PII extraction,
  mainboard rules applied to SME.
* Human-in-the-loop boundary: every output marked DRAFT; no section without its source trace; the system never
  fills `[●]` on request.

## 9. Who does what

| actor | does |
|---|---|
| **Claude Code (laptop)** | all code, offline tests, the mock model server, notebook generation, data building that needs no GPU (segmenter, masking, gates, router, MinHash, bundles), reading results back and writing the report tables |
| **Colab Pro (run by a person)** | teacher screen and extraction, baselines, training runs, evaluation generation, judge, quantisation; notebooks write to `MyDrive/sme_drhp/runs/`, synced to the laptop with Google Drive for desktop |
| **Reviewer (project owner)** | Week 0: label facts for 10 units from scratch (~2–3 h), fix the checklist per core section (~2 h), review a 20-row dry run (~1 h). Week 3: 50 judge-check scores and the blind comparison (~4–5 h). Bundles: add missing and contradictory items (~1 h). Total ~10–12 h |
| **Team members** | each runs at least one training job (A, B, ablation, seeds are 5 jobs; the 6th member runs the DPO or the AWQ export), and each can explain their part in the demo |

If the course's SSH GPU machine is available, Claude Code can run the GPU steps there directly and the Colab
hand-offs disappear. Check the programme's policy on AI-written code before submission.

**Built-in checks for AI-written code:** every stage has offline tests (the earlier projects have 26–55 each);
a mock OpenAI-compatible server returns schema-valid responses so the whole pipeline, from bundle to `.docx`,
runs on the laptop before any GPU time is spent; the 20-row dry run is reviewed by a person before any full
GPU run.

## 10. Schedule and gates

| when | work | done when |
|---|---|---|
| **Week 0** | segmenter, typed-fact schema, masking, gates, router, MinHash, mock server, tests | 20-unit dry run passes all gates on the mock |
| | teacher screen on Colab A100: Qwen3-32B vs Qwen3-30B-A3B on 30 units, 10 labelled by the reviewer | teacher chosen: precision ≥ 95%, coverage ≥ 85% |
| | checklist per core section; success criteria (7.4) recorded; ICDR Chapter IX text and SME circulars downloaded | files committed |
| **Week 1** | full teacher extraction (~2,000 calls, resumable), gates, leakage report, freeze | MANIFEST with counts, no company in both splits |
| | B0–B3 on the 200 test rows, metric harness | **gate: baseline numbers recorded, dataset frozen** |
| | ingestion for all 5 formats with provenance | 5 sample files per format parsed, tests pass |
| **Week 2** | runs A and B, ablation 1, 2 seeds | W&B dashboard |
| | retrieval corpus, embeddings, reranker, recall@k, router recall | recall table |
| **Week 3** | R0, F1, F2 on the test rows; statistics; judge; judge check; blind comparison | evaluation tables with intervals; H1–H4 marked pass/fail |
| | templates, code tables, verifier, assembler, 5 bundles end to end | H5 marked pass/fail; one full draft reviewed |
| **Week 4** | merge, AWQ, vLLM + FastAPI, Docker, latency | endpoint answers, numbers recorded |
| | model card, red-team log, 12-page report, 10-minute demo | deliverables complete |

## 11. Compute budget (Colab Pro, estimate, not measured)

| stage | GPU | units |
|---|---|---|
| teacher screen (2 candidates × 30 units) | A100 | ~8 |
| teacher extraction (~2,000 calls) | A100 (32B) or L4 (30B-A3B) | 6–22 |
| baselines B0, B1, B3 | L4 / A100 | ~6 |
| training: A, B, ablation, 2 seeds (5 runs) | L4 | ~20 |
| evaluation generation R0, F1, F2 + judge | L4 | ~10 |
| merge, AWQ, serving test | A100 | 5–11 |
| reruns (+30%) | | ~17–25 |
| **total** | | **~72–102** |

Colab Pro's 100 units a month should cover it, with a top-up only if the 32B teacher is chosen and runs are
repeated. Disconnect idle runtimes; check the per-GPU rate in the Resources panel before the first run.

## 12. What already exists and is reused

| need | existing file |
|---|---|
| SME documents and text | `bse_ipo_prospectus/out/indian_ipo_prospectus_data_2021_2026/` |
| section labels, chunker, Qwen tokenizer | `ipo_prospectus_sft/sft/{sections,chunker,tokenizer}.py`, `chunks/*.parquet` |
| extraction task schemas | `ipo_prospectus_sft/generation/templates.py` |
| teacher driver (OpenAI-compatible or Anthropic, resumable) | `ipo_prospectus_sft/generation/generate.py` |
| grounding checks | `ipo_prospectus_sft/sft/verify.py` |
| extraction metrics | `ipo_prospectus_sft/generation/evaluate.py` |
| BM25, RRF, corpus builder | `ipo_pitch_dataset/rag/`, `pe_dataroom_dataset/src/retrieval.py` |
| LLM client, judge, red-team runner | `ipo_pitch_dataset/src/{llm,judge,red_team}.py` |
| Colab notebooks | `ipo_pitch_dataset/train/*.ipynb`, `ipo_prospectus_sft/colab/make_notebook.py` |
| FastAPI + vLLM + Docker | `ipo_pitch_dataset/serve/` |
| DRHP `.docx` styling, Schedule VI section map | `drhp_template/{lib,build}.js` |
| perturbations for DPO | `ipo_pitch_dataset/src/perturb.py` (pattern) |

New code, proposed layout:

```
sme_drhp_drafter/
  ingest/     readers (docling, openpyxl, PaddleOCR, Qwen2.5-VL) with provenance, file classifier
  data/       segmenter, cleaning, [●] masking, typed facts, gates, router, distractors, MinHash, pair builder, OCR noise
  teacher/    extraction prompts, teacher screen kit, reviewer labelling sheet
  draft/      outline planner, prompt builder, template filler, code tables
  verify/     grounding, cross-section consistency, checklist, DRHP-stage check
  rag/        corpus, embeddings, reranker, recall@k
  assemble/   .docx builder (drhp_template/lib.js), review pack
  bundles/    issuer-bundle builder for the 5 held-out companies
  eval/       metrics, bootstrap, judge rubric, kappa, blind-comparison sheet
  mock/       OpenAI-compatible mock server for offline runs
  serve/      FastAPI, vLLM, Dockerfile
  colab/      make_notebook.py and notebooks (teacher, baselines, training, eval, export)
  docs/       success criteria, model card, red-team log, report outline
  tests/      offline tests
```

## 13. Risks

| risk | effect | mitigation |
|---|---|---|
| teacher misses facts | student learns to invent | coverage gate; teacher screen measures coverage first |
| fact wording copies the target | inflated similarity, copying | typed facts, 8-word overlap check |
| boilerplate shared across companies | inflated similarity | MinHash; novel-subset metrics; template baseline B2 |
| targets are final prospectuses | prices and dates in a DRHP draft | `[●]` masking; DRHP-stage check in the verifier |
| model ignores or misuses facts at inference | wrong facts in a section | distractor training, same router in training and inference, ablation 1 |
| issuer files differ from prospectus text | weaker extraction on real files | OCR-noise rows; 5 bundles; Excel by code |
| one reviewer who is also the project owner | biased human scores | blind, randomised comparisons; labels before seeing model output |
| SME rules changed in 2021–2026 | outdated drafting | weight recent years; rules only from official text |
| Colab hand-offs and session limits | lost time | resumable runs on Drive; mock server so code is right before GPU time; SSH machine if offered |
| legal liability, PII of directors | misuse as a filing | DRAFT marking, source trace, model card, human-review boundary |
| redistribution of BSE filings, client documents | licence and confidentiality issues | datasets private; no client files without permission |

## 14. Open decisions

1. Whether the course's SSH GPU machine is available (removes the Colab hand-offs).
2. The programme's policy on AI-written code.
3. Which of the 5 bundle companies is the live demo.
