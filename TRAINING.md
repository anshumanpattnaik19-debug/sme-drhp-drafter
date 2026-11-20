# Training pipeline (PLAN.md section 5, Week 0)

> A one-line-per-run record of every retraining and why it was done: [RETRAINING_LOG.md](RETRAINING_LOG.md).

Builds the training set for the SME DRHP drafter from the 455 SME offer documents already split into SEBI sections
in `../ipo_prospectus_sft/chunks/` (train 354 / test 101 documents, split by company). Everything here runs on the
laptop except the teacher and training stages, which run on Colab.

## Flow

```
chunks/*.parquet ─► units ─► sample ─► teacher (Colab) ─► rows (laptop) ─► train / test.jsonl ─► QLoRA (Colab)
                    clean      1,800 + 200 rows     2,062 calls          gates, router,
                    segment    ≤ 6 per company      typed facts          distractors,
                    mask [●]   2025-26 weighted                          precedents, MinHash
```

| stage | command | output |
|---|---|---|
| units | `python -m data.build units` | `trainset/work/units_{train,test}.jsonl` |
| sample | `python -m data.build sample` | `trainset/work/sampled_*.jsonl`, `teacher_jobs.jsonl`, `sample_plan.json` |
| teacher | Colab stage 2, or `python -m teacher.driver --jobs … --out … --endpoint … --model …` | `teacher_responses.jsonl` |
| gap-fill | `python -m teacher.gapfill jobs ...`, Colab stage 2b, then `python -m teacher.gapfill merge ...` | `gapfill_jobs.jsonl`, `gapfill_responses.jsonl`, `teacher_responses_merged.jsonl` |
| rows | `python -m data.build rows --responses <file>` | `trainset/out/{train,test,train_no_distractors}.jsonl`, `MANIFEST.json`, `GATES_REPORT.md` |
| dry run | `python -m data.build dry-run --n 20` | the same on 20 units with the in-process mock teacher |

## What each part does

| file | job |
|---|---|
| `data/corpus.py` | rebuilds each section's text from its chunks (removes the 100-token overlap) |
| `data/clean.py` | drops running headers and page numbers, rejoins PDF-broken words ("inclu ding"), flags flattened tables |
| `data/segment.py` | one unit per real sub-heading (capitals or title case); risk factors by number, short ones grouped up to 4; 150-1,500 tokens |
| `data/mask.py` | DRHP stage: offer price, price band, issue size and proceeds in ₹, offer dates, lot size → `[●]`; "Prospectus" → "Draft Red Herring Prospectus" |
| `data/facts.py` | typed-fact schema and the gates: precision, leakage (8-word overlap), masking, coverage (all figures and dates, ≥ 90% of names) |
| `data/pairs.py` | sampling to the PLAN.md budget; drafting rows (own facts + about as many router-ranked distractors, precedent in half) and extraction rows (30% OCR-noised) |
| `data/minhash.py` | flags test targets with Jaccard ≥ 0.6 to any train unit, so metrics can be reported on the novel subset |
| `data/prompts.py` | the student's prompt format, **shared with the app** (`draft/writer.py` drafts one sub-heading per call in this format) |
| `teacher/prompts.py`, `teacher/driver.py` | the extraction prompt and a resumable OpenAI-compatible driver (refuses to run without an endpoint) |
| `teacher/screen.py`, `teacher/label_sheet.py` | the Week 0 teacher screen and your labelling workbook |
| `mock/server.py` | OpenAI-compatible mock that returns schema-valid facts, so every stage runs before GPU time |
| `colab/make_notebook.py` | writes `colab/sme_drhp_colab.ipynb` and the Drive package `colab/sme_drhp_colab.zip` |

## Week 0 checklist

| who | task | where |
|---|---|---|
| you (~1 h) | review the 187 facts already entered for the 10 units in `trainset/screen/reviewer_labels.xlsx` (correct, add or delete rows), then `python -m teacher.label_sheet read --xlsx trainset/screen/reviewer_labels.xlsx` | laptop |
| you (~2 h) | fix the mandatory-item checklist per core section (replaces the placeholders in `draft/outline.py`) | laptop |
| team member | upload `colab/sme_drhp_colab.zip` and `reviewer_labels.json` to `MyDrive/sme_drhp/`, run notebook stages 0-1 on an A100 | Colab |
| everyone | pick the teacher from `SCREEN_REPORT.md` (precision ≥ 95%, coverage ≥ 85%) | – |
| you (~1 h) | review 20 rows of the first real `rows` run before the full extraction | laptop |

## Decisions taken while building (differences from PLAN.md)

* **Previous-unit summary is extractive** (first two sentences, ≤ 60 words) rather than teacher-written. The app can
  build the same summary at inference from the sub-section it just drafted, so training and inference match, and it
  saves about 1,000 teacher calls.
* **Context units for the test split**: 62 extra units (teacher facts only, no rows) so test companies, which have one
  or two rows each, still get distractor facts from their other sub-sections. Teacher calls: 2,062 instead of ~2,000.
* **Distractors are router-ranked**: the inputs are the unit's own facts plus about as many of the router's best-ranked
  facts from the company's other units (hard negatives). The router's own recall of the gold facts in its top 40 is
  reported separately (`router_recall`).
* **Units with more than 40 facts are not drafting rows**: they would not fit with their distractors. Units with no
  facts at all (pure boilerplate) fail the gate; templates cover them.
* **Gates checked against correct labels**: the 10 labelled screen units must pass the gates. The first version failed
  all 10 on its own false alarms, so the gates were changed: names are capitalised tokens that the corpus does not
  usually write in lower case (`trainset/work/common_words.json`, 9,558 words), acronyms are terms not names, the
  leakage rule applies to free-text facts only (not names, codes or quoted titles), and a masked value only drops a
  fact when it no longer appears in the target. All 10 now pass; the issue-expense break-up is masked as price-dependent.
* **Flattened tables are cut out of drafting targets** (`data/clean.strip_tables`): runs of three or more numbers with
  their row labels. The app builds ICDR tables from the issuer's schedules in code, so the model is not trained to
  write them; prose with figures stays. Extraction rows keep the full text.
* **Gap-fill pass** (`teacher/gapfill.py`): drafting units that fail the coverage gate get a second, short teacher
  call listing the figures, dates and names the first pass missed, as written in the passage. Only units that could
  still become rows are sent (everything missing is listed, and kept plus missing facts fit 40): 497 of 1,150
  drafting units. New facts are appended and pass through the same gates. The coverage rule itself is not relaxed:
  a target figure with no fact would teach the model to invent figures.
* **Precision is reported per fact** (share of the teacher's facts found in the source). The first report averaged
  per unit and counted units with no facts as 0.
* **Run A beats the base on held-out loss but not on greedy drafts** (1 Nov 2026): test-draft loss 1.29 against the
  base's 1.84 (extraction 0.064 against 0.148), yet with loops trimmed its drafts used 0.44 of the target's facts
  against the base's 0.48; both loop under greedy decoding (43 and about 28 of 89 drafts hit the cap). Run C
  (r32, 3 epochs, drafting rows twice) is next, and a configuration now has to beat the base on **held-out loss** on
  the test drafts before seed or ablation runs. A repetition penalty was tried and dropped: it changed dates and
  figures. Generated drafts are cut at a loop with `data.prompts.trim_repeats`.
* **Run C overfit; run A is the configuration** (1 Nov 2026): run C's training loss fell to about 0.12 by epoch 3,
  but its held-out loss is worse than run A's (drafting 1.587 against 1.291, extraction 0.076 against 0.064; base
  1.841 and 0.148). Showing each drafting row 6 times (3 epochs, weight 2) memorised the targets. More epochs or
  drafting weight do not help; run B (r64, lr 1e-4, 2 epochs) is the remaining comparison.
* **The adapter causes the loops; the earlier B0 was not the base** (1 Nov 2026): the first B0 predictions still had
  the adapter attached, so "run A loops as much as the base" was run A against itself. A true base run loops on 4 of
  89 drafts, run A on 38 (mostly objects, promoters and management). With loops trimmed, run A uses distractors less
  (0.109 against 0.142) and writes fewer unknown figures (0.55 against 0.75 per draft) at the same own-fact use
  (0.47), and its extraction recall is 0.71 against the base's 0.43. The loops are the problem to fix next.
* **vLLM 0.32 has no bitsandbytes support** (2 Nov 2026): it cannot load the 4-bit base Unsloth trains on, so vLLM
  serves the adapter on the bf16 base and anything on the 4-bit base (held-out loss, the 4-bit loop check) runs
  through Unsloth. Low-temperature sampling (0.3) did not reduce run A's loops (34 against 38 greedy).
* **The loops are learned, not a serving effect** (2 Nov 2026): on the 4-bit training base (Unsloth), 14 of 20
  drafts that looped in vLLM still run to the cap. Run A repeats DRHP boilerplate verbatim ("Except as disclosed in
  the section titled ... beginning on page 200"), flattened director-table rows and machine lists. The targets are not
  loopy and the loss is on responses only, so the next test is gentler training: run B (r64, alpha 64, lr 1e-4).
* **Run B held-out loss ties run A** (3 Nov 2026): r64, alpha 64, lr 1e-4, 2 epochs (182 steps, 1 h 13 min on an L4)
  gives drafting 1.300 and extraction 0.065 (A: 1.291 and 0.064; base 1.841 and 0.148). Held-out loss cannot choose
  between them, so the choice rests on the greedy loop count from cell 17 (A: 38 of 89 drafts trimmed at a loop). Run B gives
  47 cap hits and 42 looping drafts, so gentler training does not stop the loops and run A stays. What run A repeats:
  26 of its 38 loops are generic DRHP sentences ("The Offer is being made pursuant to a fresh issue ..."), 7 are page
  cross-references and 5 are table rows. Looping and clean drafts get the same fact density (about 2.9 own facts per
  100 target words), so missing facts do not explain them; looping targets are somewhat longer (median 232 words
  against 194). A repetition penalty of 1.05 (merged run A) cut loops from 40 to 31 only. Separately, 21 of 89 run A
  drafts cite "on page N" while only 2 prompts carry a page number in FACTS: 101 of 657 drafting targets contain
  "beginning on page", so the model invents page numbers.
* **Page numbers are cut from cross-references** (3 Nov 2026, `data.clean.strip_page_refs`): "see “Risk Factors” on
  page 25 of this Draft Prospectus" becomes "see “Risk Factors”". No input carries the page layout of the document being
  drafted, so a page number in a target can only teach the model to invent one. Applied to targets, section outlines,
  previous-sub-section summaries and precedents in the build (`data/pairs.py`, `teacher/gapfill.py`) and in the app's
  prompts (`data/prompts.drafting_messages`). The current files were not rebuilt: `python -m data.nopage trainset/out`
  derives `train_nopage.jsonl` and `test_nopage.jsonl` from them (185 of 657 train and 31 of 89 test drafting targets
  changed, FACTS identical), so run A2 differs from run A only here. A rebuild would also change which units pass the
  figures gate.
* **Run A2 (page-free data) loops as much as run A** (3 Nov 2026): held-out drafting 1.316 against the base's 1.856 on
  `test_nopage.jsonl` (29% lower; run A 30% lower on `test.jsonl`), extraction 0.065; greedy predictions give 50 cap hits
  and 43 looping drafts (A 42 and 38). Three runs with different rank, learning rate and data (A, B, A2) all loop on 38-43
  of 89 drafts while the base loops on 4, so the loops come with fine-tuning on these targets as such. Next cheap test is
  at decoding: a repetition penalty on drafts (`REP` in cell 17).
* **The merged-model files are invalid** (found 4 Nov 2026): merging an adapter trained on the 4-bit base into bf16
  weights broke the model, so `predictions_test_merged*.jsonl` (and the repetition-penalty 1.05 result above, which was
  run on the merged model) say nothing about penalties. Penalties are now tested on the unmerged adapter through
  vLLM's LoRA path (stage 5, cell 20).
* **DPO on top of run A, with a frequency penalty, stops the loops** (4 Nov 2026, stage 5): run A drafted 400 train
  prompts; the 236 that looped or hit the cap gave 233 pairs (chosen = the gold sub-section, rejected = run A's own
  draft cut at 1,200 tokens; mostly management, promoters, objects and business). DPO with beta 0.1, lr 1e-5,
  2 epochs, a frozen copy of adapter A as the reference (TRL `ref_adapter_name`) gives run **A_dpo**: held-out
  drafting 1.319 and extraction 0.065 (A 1.291 and 0.064), so the SFT fit is kept. Scored with `data.score_preds` on
  the 89 test drafts (greedy, stop-on-loop or one shot):

  | | loops | caps | length / gold | own-fact use | distractor use | unknown figures / draft |
  |---|---|---|---|---|---|---|
  | base (B0) | 4 | 1 | 1.02 | 0.509 | 0.512 | 0.24 |
  | A | 38 | 39 | 1.47 | 0.494 | 0.429 | 0.43 |
  | A, frequency 0.3 | 23 | 0 | 1.44 | 0.593 | 0.476 | 0.53 |
  | A, repetition 1.1 | 13 | 11 | 2.21 | 0.589 | 0.488 | 0.42 |
  | A_dpo | 20 | 3 | 1.09 | 0.517 | 0.381 | 0.36 |
  | **A_dpo, frequency 0.3** | **4** | **0** | **0.98** | **0.607** | 0.429 | 0.42 |
  | A_dpo, frequency 0.5 | 0 | 0 | 0.93 | 0.514 | 0.452 | 0.54 |

  **A_dpo with frequency penalty 0.3 is the configuration** (cell 17 default `FREQ = 0.3`, drafting only; extraction
  stays plain greedy). Limits: DPO training was very easy (reward accuracy 1.0, loss about 0.003): in 217 of 233 pairs
  the rejected text is the longer one, so part of what DPO learned may be "shorter"; drafts still come out at the gold
  length. Own facts are those whose value appears in the gold text (test rows do not mark them), so these numbers do
  not equal the earlier 0.47 / 0.11. A_dpo's extraction output has not been generated yet (cell 17 for `A_dpo`).
* **Full test run, A_dpo against the base, same decoding** (6 Nov 2026, cell 17, `FREQ = 0.3` on drafts, extraction
  greedy; `predictions_test_f03.jsonl` in `drive/runs/A_dpo` and `drive/runs/B0`; scores in `drive/SCORES_6NOV.json`):

  | | loops | caps | length / gold | own-fact use | distractor use | unknown figures / draft | unknown dates / draft | extraction valid | precision | recall |
  |---|---|---|---|---|---|---|---|---|---|---|
  | base, greedy | 4 | 1 | 1.02 | 0.509 | 0.512 | 0.24 | 0.02 | 50 | 0.462 | 0.279 |
  | base, frequency 0.3 | 3 | 0 | 1.00 | 0.530 | 0.571 | 0.22 | 0.03 | 49 | 0.484 | 0.289 |
  | A, greedy | 38 | 39 | 1.47 | 0.494 | 0.429 | 0.43 | 0.02 | 47 | 0.571 | 0.479 |
  | **A_dpo, frequency 0.3** | **1** | **0** | 0.96 | **0.574** | **0.464** | 0.39 | 0.10 | 47 | **0.631** | 0.452 |

  Against the base decoded the same way, A_dpo loops less, uses more own facts and fewer distractors, and its
  extraction is far better (precision 0.63 vs 0.48, recall 0.45 vs 0.29; 21 of the base's 50 answers come in code
  fences, scored after stripping them). Its 3 cap hits are all extraction (two MD&A, one industry), which is also why
  3 of 50 JSON answers are invalid, as in run A. Against run A, DPO moved extraction slightly (precision 0.57 → 0.63,
  recall 0.48 → 0.45), although the pairs were drafting only. **Open problem: invented figures and dates.** A_dpo
  writes 0.39 figures and 0.10 dates per draft that are in no input, against the base's 0.22 and 0.03; fine-tuning
  raised this (run A 0.43) and DPO did not lower it. This is the measure behind success criteria H1 and H2, so the
  verifier stage (`verify/checks.py`) has to catch these before a draft is shown. Own-fact use is 0.574 here and 0.607
  in the stage 5 re-test of the same setting: a different prompt path (text against token ids) and vLLM batching, so
  read it as about 0.57–0.61.
* **Seeds and ablation 1** (run by a teammate 11–12 Nov 2026, SFT only, run A's settings; work plan
  `WORKPLAN_ablation_seeds.docx`; files in `drive/runs/{seed2,seed3,ablation1}`, the teammate's log in
  `drive/logs/FAILURES_aisharmaakshay.md`; scores in `drive/SCORES_12NOV.json`). Same `train.jsonl`, `test.jsonl` and
  `train_no_distractors.jsonl` as the laptop (checksums match) and the same code package as run A. Cell 17 ran
  **greedy without the frequency penalty** (files `predictions_test.jsonl`, not `_f03`; FAILURE_LOG 27), so they compare
  with run A greedy, not with A_dpo:

  | | seed | data | held-out drafting / extraction | loops | caps | length / gold | own-fact use | distractor use | unknown figures / draft | extraction precision / recall |
  |---|---|---|---|---|---|---|---|---|---|---|
  | A | 3407 | train | 1.291 / 0.064 | 38 | 39 | 1.47 | 0.494 | 0.429 | 0.43 | 0.571 / 0.479 |
  | seed2 | 11 | train | 1.285 / 0.063 | 35 | 39 | 1.61 | 0.493 | 0.440 | 0.35 | 0.587 / 0.451 |
  | seed3 | 23 | train | 1.282 / 0.063 | 38 | 37 | 1.25 | 0.528 | 0.500 | 0.38 | 0.659 / 0.625 |
  | ablation1 | 3407 | no distractors | 1.287 / 0.063 | **72** | **76** | 1.54 | 0.558 | **0.583** | 4.78 (0.39 without one draft) | 0.636 / 0.511 |

  **Seed spread** (A, seed2, seed3): held-out loss moves by under 0.01 and loops by 3, but the generation measures
  move a lot: own-fact use 0.49–0.53, distractor use 0.43–0.50, extraction precision 0.57–0.66 and recall 0.45–0.63.
  A difference between configurations smaller than about 0.04 in fact use, 0.07 in distractor use or 0.17 in
  extraction recall can be seed noise. Read against that: A_dpo's lead over the base on distractor use (0.46 vs 0.57)
  and extraction precision (0.63 vs 0.48) is larger than the seed spread, its lead on own-fact use (0.57 vs 0.53) is
  not, and its recall lead (0.45 vs 0.29) is about the size of the spread. Three seeds is a small sample, and these are
  SFT seeds, not DPO seeds.
  **Ablation 1: distractor training helps.** Without distractor facts the model uses a wrong-section fact in 58% of
  drafts (seeds 43–50%) and loops on twice as many drafts (72 against 35–38); held-out loss cannot tell them apart.
  Its 4.78 unknown figures per draft come from one objects draft (391 numbers in a list that `trim_repeats` does not
  cut); without it the rate is about 0.39, as for the seeds.
* **Token counts are estimated** (1.3 tokens per word). The longest dry-run row is about 1,600 of the 6,144 limit;
  check with the Qwen tokenizer on Colab before training.

* **v2: a third skill, question answering with guardrails** (decided 14 Nov 2026; NEXT_STEPS part E). The brief's
  Track A is a domain-adapted *assistant*, and the app's assistant was answering with a model never trained for it.
  Rows use the assistant's own prompt (`data/prompts.qa_messages`: numbered EVIDENCE of 5 passages from the same
  company, then the QUESTION). Answerable rows come from teacher pairs gated on a verbatim quote that carries every
  figure and date of the answer; the answering passage sits among 4 distractors with none of the answer's figures,
  and every sentence of the target cites it as [n]. Unanswerable rows drop that passage and name the document to
  request. Guardrail rows (templated, several wordings each): an injected instruction in a distractor passage (answer,
  and say it was ignored), investment advice, DRHP-stage offer terms ([●]), personal identifiers, and omitting or
  softening a disclosure. 300 train and 60 test rows; test companies are only in the test split. Earlier runs (A to
  A_dpo, seeds, ablation) stay as the v1 results; v2 is run A's settings on `train_v2.jsonl` (`A_qa`), then DPO.

## Known limits

* Headings are found by layout heuristics; a few table headers and names in tables still pass. They only affect the
  outline and the sub-heading text, and the gates still apply to every unit.
* OCR noise is synthetic (dropped spaces, confusable characters); `data/noise.render_ocr` gives a real OCR round trip
  for a small slice if wanted.
* The Colab notebook has **not been run on a GPU**. Library versions (vLLM 0.10.1.1, Unsloth, TRL ≥ 0.19) are pinned
  but untested together; stage 0 is where to fix them.
* The evaluation harness (grounding, fact use, distractor leakage, checklist coverage, ROUGE/BERTScore, judge, bootstrap)
  is Week 1 and not built yet. The notebook writes `predictions_test.jsonl` for it.
