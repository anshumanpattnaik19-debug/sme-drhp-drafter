# Next steps: from teacher output to the first training run

Paths: **Laptop** = `C:\Users\anshu\Desktop\SLM -2\SLM -2\sme_drhp_drafter\`. **Drive** = `My Drive/sme_drhp/`
(the folder the notebook uses; not `DRHP Drafter`). **Colab** = `/content/sme/` after stage 0.

Done so far (1 Nov 2026): runs A and C trained; run A is the configuration (beats the base on held-out loss and on
fact use, but its greedy drafts loop; see FAILURE_LOG 18 and `SESSION_HANDOFF.md`). screen scored (32B kept), full extraction (2,038 of 2,062 parsed), gap-fill (492 of 497),
merge and rebuild: 1,446 train rows (657 drafting) and 139 test rows (89 drafting). Parts A and B1–B3 are done; next
is B4, the review of `trainset/out/REVIEW_20.md`.

## A. Colab, A100 runtime: screen score and gap-fill

| step | do | file in | file out |
|---|---|---|---|
| A1 | replace the package on Drive (choose **Replace**) | Laptop `colab/sme_drhp_colab.zip` | Drive `sme_drhp_colab.zip` |
| A2 | upload the new notebook (File → Upload notebook) | Laptop `colab/sme_drhp_colab.ipynb` | – |
| A3 | upload the screen labels | Laptop `trainset/screen/reviewer_labels.json` | Drive `screen/reviewer_labels.json` |
| A4 | Runtime → Change runtime type → **A100**; run **Stage 0** and the **vLLM install** cell | Drive `sme_drhp_colab.zip` | Colab `/content/sme/` |
| A5 | check the package is the new one: `!ls /content/sme/teacher/` must list `gapfill.py` and `serving.py` | – | – |
| A6 | run the **score cell** (after the Stage 1 loop; skip the loop itself) | Drive `screen/responses_*.jsonl`, `screen/reviewer_labels.json` | Drive `screen/SCREEN_REPORT.md` (paste it in the chat) |
| A7 | run the **Stage 2b gap-fill** cell (about 500 short calls, roughly 1 hour) | Colab `trainset/work/gapfill_jobs.jsonl` | Drive `work/gapfill_responses.jsonl` |
| A8 | download the gap-fill responses: `from google.colab import files; files.download('/content/drive/MyDrive/sme_drhp/work/gapfill_responses.jsonl')` | – | Laptop `Downloads\gapfill_responses.jsonl` |
| A9 | Runtime → Disconnect and delete runtime | – | – |

Stage 2b runs on its own after Stage 0 (it no longer needs the Stage 1 cell). The labels for the 10 screen units still
need your review (`trainset/screen/reviewer_labels.xlsx`); the vs-reviewer numbers are provisional until then.

## B. Laptop: merge, rebuild, review, upload

| step | do | file in | file out |
|---|---|---|---|
| B1 | tell me the file is in Downloads; I copy it to `trainset/work/` | `Downloads\gapfill_responses.jsonl` | Laptop `trainset/work/gapfill_responses.jsonl` |
| B2 | merge: `python -m teacher.gapfill merge --responses trainset/work/teacher_responses.jsonl --gapfill trainset/work/gapfill_responses.jsonl --out trainset/work/teacher_responses_merged.jsonl` | the two response files | `trainset/work/teacher_responses_merged.jsonl` |
| B3 | rebuild: `python -m data.build rows --responses trainset/work/teacher_responses_merged.jsonl` (about 15 min) | merged responses | `trainset/out/train.jsonl`, `test.jsonl`, `train_no_distractors.jsonl`, `MANIFEST.json`, `GATES_REPORT.md` |
| B4 | review 20 rows (a review file will be prepared) | `trainset/out/` | your notes in the chat |
| B5 | upload the rows (create the `out` folder if missing) | `trainset/out/train.jsonl`, `test.jsonl`, `train_no_distractors.jsonl`, `MANIFEST.json` | Drive `out/` |

## C. Colab, L4 runtime: training

Run A (1 Nov 2026) beats the base on held-out loss (drafting 1.29 vs 1.84, extraction 0.064 vs 0.148) but its greedy drafts loop as much as the base's (FAILURE_LOG item 18). Next is
**run C** (r32, lr 2e-4, 3 epochs, drafting rows twice) judged by **held-out loss** on the test drafts. Hold B,
ablation1, seed2 and seed3 until a configuration beats the base.

Run C done (1 Nov 2026): held-out drafting 1.587, extraction 0.076, worse than run A (1.291, 0.064), so it overfit.
**Run A is the configuration.** C6 is not needed (run A's numbers are already recorded). Next is C7 and C8 with
`RUN = 'A'`, then the laptop comparison. Run B (`RUN = 'B'`, cells 15 and 16) is optional, on a second runtime.

| step | do | notes |
|---|---|---|
| C0 | replace the zip on Drive `sme_drhp/` (choose **Replace**) and upload the new notebook | the predictions cell imports `trim_repeats` from the new package |
| C1 | Runtime → Change runtime type → **L4** | |
| C2 | run **Stage 0**, the **vLLM install** cell (4) and the **Stage 3–4 install** cell (13) | |
| C3 | **Runtime → Restart session**, then **Stage 0** again | |
| C4 | RUNS cell (14) with `RUN = 'C'`, then the **training** cell (15) | about 395 steps, roughly 2.5–3 h; first line `rows 2103 \| resume from None`; checkpoints in Drive `runs/C/ckpt/` |
| C5 | **held-out loss** cell (16), straight after training | prints drafting and extraction loss for run C and the base; writes `runs/C/heldout_loss.json`. Paste the two lines |
| C6 | run A's held-out loss for comparison: Restart session, Stage 0, the install check, RUNS with `RUN = 'A'`, then cell 16 | about 5 min; writes `runs/A/heldout_loss.json` |
| C7 | predictions (cell 17) for **A**: Restart session, Stage 0, RUNS with `RUN = 'A'`, cell 17 | now caps drafting at 2,200 and extraction at 3,000 tokens, trims drafts at a loop, and records `finish` and the raw text |
| C8 | B0 with the new cell: set `BASELINE = True` in cell 17 and run it after a restart | replaces the old B0 file, so B0 and A are generated the same way |
| C9 | sampled drafts: upload the new notebook (the zip is unchanged), Restart session, Stage 0, RUNS with `RUN = 'A'`, set `TEMP = 0.3` in cell 17, run it; then restart and repeat with `BASELINE = True` | done 1 Nov 2026: C7 and C8 (greedy), see FAILURE_LOG item 18. C9 writes `predictions_test_t03.jsonl` in `runs/A/` and `runs/B0/`; download as `predictions_A_t03.jsonl` and `predictions_B0_t03.jsonl`. Extraction stays greedy |

## Not yet tested

- Stage 2b has run only against the mock teacher (test passes); not yet on the real teacher.
- Stages 3–4 have never run: Unsloth, TRL and vLLM 0.32 have not been installed together on this image, and the
  Pillow pin is untested. Paste the first error if one appears; it goes in `FAILURE_LOG.md`.
- B1 (2-shot baseline) and B3 (teacher 2-shot) have no notebook cell yet; the evaluation harness (Week 1) is not built.
