# Evaluation report

Built 14 Nov 2026 17:23 by `python -m evaluate.run`. Test rows: 89 drafting and 50 extraction from 62 companies. 95% intervals: percentile bootstrap over companies, 1000 resamples.

System judged against the success criteria: **A_dpo_f03_verified**. The plan judges F2 (fine-tuned + RAG); until F2 is run, this system stands in.

## Success criteria (PLAN.md 7.4)

| | status | evidence |
|---|---|---|
| H1 | partly met | grounding 0.990 [0.978, 0.998] (needs >= 0.98); R0 (base + RAG) not run, so the interval comparison is pending |
| H2 | pass | invented-figure rate 0.000 [0.000, 0.000] of drafts (needs <= 0.02) |
| H3 | pending | checklist coverage needs the reviewer's mandatory-item checklist (draft/outline.py holds placeholders) and whole-section drafts; test rows are single sub-sections |
| H4 | pending | needs the LLM judge scores and the reviewer's blind comparison |
| H5 | pending | needs the 5 issuer bundles run end to end (one, Ashtavira, exists) |

## Systems

Drafting: grounding = figures, dates and names in the draft found in the issuer's inputs (the prompt without its precedent); invented rates = share of drafts with at least one figure / date not in those inputs; fact use = share of the facts that the filed text uses which the draft also uses; distractor leakage = share of drafts using a fact the filed text does not use. Extraction: value-level precision, recall and F1.

| system | file | grounding | grounding_figures | invented_fig_rate | invented_date_rate | fact_use | distractor_leakage | rouge_l | loop_rate | len_ratio | extract_precision | extract_recall | extract_f1 | json_valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0_f03 | `drive/runs/B0/predictions_test_f03.jsonl` | 0.865 [0.787, 0.932] | 0.794 [0.660, 0.915] | 0.202 [0.114, 0.310] | 0.045 [0.011, 0.094] | 0.502 [0.432, 0.584] | 0.571 [0.485, 0.662] | 0.250 [0.223, 0.286] | 0.034 [0.000, 0.075] | 1.001 [0.828, 1.203] | 0.455 [0.324, 0.575] | 0.272 [0.185, 0.391] | 0.340 [0.242, 0.455] | 0.980 [0.933, 1.000] |
| B0_f03_verified | `drive/runs/B0/predictions_test_f03_verified.jsonl` | 0.960 [0.933, 0.984] | 0.970 [0.919, 1.000] | 0.034 [0.000, 0.080] | 0.000 [0.000, 0.000] | 0.499 [0.427, 0.582] | 0.560 [0.468, 0.645] | 0.251 [0.223, 0.287] | 0.034 [0.000, 0.075] | 0.999 [0.826, 1.201] | 0.455 [0.324, 0.575] | 0.272 [0.185, 0.391] | 0.340 [0.242, 0.455] | 0.980 [0.933, 1.000] |
| B2_template | `drive/runs/B2/predictions_test.jsonl` | 0.826 [0.636, 0.962] | 0.714 [0.300, 0.944] | 0.045 [0.010, 0.092] | 0.000 [0.000, 0.000] | 0.068 [0.040, 0.105] | 0.060 [0.013, 0.113] | 0.227 [0.187, 0.272] | 0.022 [0.000, 0.060] | 1.119 [0.893, 1.396] | – | – | – | – |
| A_greedy | `drive/runs/A/predictions_test.jsonl` | 0.856 [0.787, 0.919] | 0.789 [0.695, 0.874] | 0.247 [0.161, 0.342] | 0.022 [0.000, 0.060] | 0.523 [0.446, 0.608] | 0.429 [0.303, 0.531] | 0.265 [0.239, 0.297] | 0.427 [0.325, 0.539] | 1.467 [1.028, 1.977] | 0.571 [0.449, 0.688] | 0.479 [0.304, 0.669] | 0.521 [0.380, 0.656] | 0.940 [0.854, 1.000] |
| A_greedy_verified | `drive/runs/A/predictions_test_verified.jsonl` | 0.929 [0.868, 0.972] | 0.922 [0.824, 0.989] | 0.067 [0.022, 0.120] | 0.000 [0.000, 0.000] | 0.520 [0.445, 0.606] | 0.393 [0.284, 0.484] | 0.266 [0.239, 0.297] | 0.427 [0.325, 0.539] | 1.441 [0.992, 1.930] | 0.571 [0.449, 0.688] | 0.479 [0.304, 0.669] | 0.521 [0.380, 0.656] | 0.940 [0.854, 1.000] |
| seed2_greedy | `drive/runs/seed2/predictions_test.jsonl` | 0.827 [0.721, 0.919] | 0.730 [0.587, 0.869] | 0.225 [0.143, 0.304] | 0.056 [0.012, 0.105] | 0.507 [0.414, 0.607] | 0.440 [0.333, 0.545] | 0.262 [0.230, 0.297] | 0.393 [0.275, 0.518] | 1.612 [1.168, 2.125] | 0.587 [0.452, 0.716] | 0.451 [0.290, 0.645] | 0.510 [0.374, 0.654] | 0.920 [0.827, 1.000] |
| seed3_greedy | `drive/runs/seed3/predictions_test.jsonl` | 0.819 [0.726, 0.903] | 0.745 [0.612, 0.863] | 0.303 [0.224, 0.391] | 0.079 [0.032, 0.130] | 0.502 [0.409, 0.602] | 0.500 [0.375, 0.615] | 0.257 [0.226, 0.291] | 0.427 [0.330, 0.533] | 1.253 [0.965, 1.589] | 0.657 [0.539, 0.763] | 0.624 [0.532, 0.721] | 0.640 [0.543, 0.718] | 0.960 [0.898, 1.000] |
| ablation1_greedy | `drive/runs/ablation1/predictions_test.jsonl` | 0.509 [0.259, 0.917] | 0.336 [0.138, 0.895] | 0.225 [0.134, 0.319] | 0.079 [0.030, 0.135] | 0.576 [0.496, 0.665] | 0.583 [0.462, 0.703] | 0.253 [0.229, 0.284] | 0.809 [0.721, 0.888] | 1.539 [1.151, 1.930] | 0.631 [0.498, 0.747] | 0.508 [0.308, 0.707] | 0.563 [0.395, 0.702] | 0.940 [0.812, 1.000] |
| A_dpo_f03 | `drive/runs/A_dpo/predictions_test_f03.jsonl` | 0.871 [0.805, 0.929] | 0.820 [0.728, 0.911] | 0.146 [0.081, 0.218] | 0.067 [0.020, 0.135] | 0.555 [0.496, 0.615] | 0.464 [0.346, 0.575] | 0.263 [0.240, 0.289] | 0.011 [0.000, 0.036] | 0.959 [0.810, 1.102] | 0.631 [0.501, 0.750] | 0.452 [0.283, 0.703] | 0.527 [0.371, 0.702] | 0.940 [0.850, 1.000] |
| A_dpo_f03_verified | `drive/runs/A_dpo/predictions_test_f03_verified.jsonl` | 0.990 [0.978, 0.998] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.553 [0.494, 0.612] | 0.452 [0.342, 0.565] | 0.264 [0.241, 0.291] | 0.011 [0.000, 0.036] | 0.953 [0.806, 1.094] | 0.631 [0.501, 0.750] | 0.452 [0.283, 0.703] | 0.527 [0.371, 0.702] | 0.940 [0.850, 1.000] |

## Paired differences: A_dpo_f03_verified minus each system

Same test rows, companies resampled together; p is two-sided.

| against | grounding | grounding_figures | invented_fig_rate | invented_date_rate | fact_use | distractor_leakage | rouge_l | loop_rate | extract_precision | extract_recall | extract_f1 | json_valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0_f03_verified | +0.030 [+0.003, +0.059] p=0.028 | +0.030 [+0.000, +0.081] p=0.106 | -0.034 [-0.080, +0.000] p=0.106 | +0.000 [+0.000, +0.000] p=1.000 | +0.054 [-0.025, +0.136] p=0.160 | -0.107 [-0.216, -0.010] p=0.046 | +0.013 [-0.007, +0.034] p=0.218 | -0.022 [-0.070, +0.022] p=0.446 | +0.176 [+0.072, +0.291] p=0.000 | +0.181 [+0.056, +0.368] p=0.002 | +0.187 [+0.074, +0.323] p=0.000 | -0.040 [-0.141, +0.043] p=0.568 |
| B2_template | +0.164 [+0.026, +0.353] p=0.030 | +0.286 [+0.059, +0.700] p=0.030 | -0.045 [-0.091, -0.010] p=0.030 | +0.000 [+0.000, +0.000] p=1.000 | +0.484 [+0.432, +0.536] p=0.000 | +0.393 [+0.282, +0.507] p=0.000 | +0.037 [+0.002, +0.070] p=0.044 | -0.011 [-0.053, +0.024] p=0.760 | – | – | – | – |
| A_dpo_f03 | +0.118 [+0.064, +0.181] p=0.000 | +0.180 [+0.090, +0.275] p=0.000 | -0.146 [-0.218, -0.081] p=0.000 | -0.067 [-0.134, -0.020] p=0.006 | -0.002 [-0.005, +0.000] p=0.264 | -0.012 [-0.037, +0.000] p=0.722 | +0.001 [+0.001, +0.002] p=0.000 | +0.000 [+0.000, +0.000] p=1.000 | +0.000 [+0.000, +0.000] p=1.000 | +0.000 [+0.000, +0.000] p=1.000 | +0.000 [+0.000, +0.000] p=1.000 | +0.000 [+0.000, +0.000] p=1.000 |

## Known limits

* Figures follow `data.facts.figures`: years, page and legal references and list numbers at a line start are not figures, but list numbers inside a flattened table ("9. ... 10. Spouse Sister(s)") are, which is why B2, which cannot invent a figure, still shows a small invented-figure rate. Names follow `data.facts.proper_names`, so capitalised terms can count as names.
* Checklist coverage, BERTScore and the LLM judge are not computed here yet.
