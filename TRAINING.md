# Training pipeline (PLAN.md section 5, Week 0)

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
* **Token counts are estimated** (1.3 tokens per word). The longest dry-run row is about 1,600 of the 6,144 limit;
  check with the Qwen tokenizer on Colab before training.

## Known limits

* Headings are found by layout heuristics; a few table headers and names in tables still pass. They only affect the
  outline and the sub-heading text, and the gates still apply to every unit.
* OCR noise is synthetic (dropped spaces, confusable characters); `data/noise.render_ocr` gives a real OCR round trip
  for a small slice if wanted.
* The Colab notebook has **not been run on a GPU**. Library versions (vLLM 0.10.1.1, Unsloth, TRL ≥ 0.19) are pinned
  but untested together; stage 0 is where to fix them.
* The evaluation harness (grounding, fact use, distractor leakage, checklist coverage, ROUGE/BERTScore, judge, bootstrap)
  is Week 1 and not built yet. The notebook writes `predictions_test.jsonl` for it.
