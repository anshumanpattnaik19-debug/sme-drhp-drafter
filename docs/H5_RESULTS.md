# H5 results and draft QC

Run: VM job 64 (`vm/h5.sbatch`), the merged A_qa_dpo model served by vLLM, all five bundles through the app's API.
Outputs pulled to `build/h5_job64/` (not in git). Measurement: `vm/h5_measure.py`. Draft QC: `vm/h5_qc.py`.

## 1. Grounding (H5 criterion: zero invented figures, traced to the bundle files)

| Bundle | Facts | Values checked | Ungrounded | Grounded |
|---|---|---|---|---|
| Ashtavira | 4,436 | 2,188 | 0 | 100.00% |
| Kestrel | 2,070 | 1,774 | 0 | 100.00% |
| Bhuvanam | 2,071 | 1,837 | 1 | 99.95% |
| Tavanvi | 2,068 | 1,692 | 0 | 100.00% |
| Oakvale | 2,070 | 1,795 | 0 | 100.00% |

The one ungrounded value (Bhuvanam, objects section) is a truncated sentence: the paragraph ends "...Section
62(1)(c) of the Companies Act, 201" with no closing text. It is the cut-off defect in section 2, not an invented
figure. H5 therefore does not pass strictly: four bundles have zero, Bhuvanam has one.

Job 63 (earlier run, before the page-footer and table-cell fixes): 0, 4, 1, 1, 2 ungrounded across the same bundles.
The footer and table fixes removed the "Page 2" references and the unmasked table dates.

## 2. Draft QC (client grade)

The grounding check passes the drafts, but a QC read finds defects that would not be acceptable in a client draft.

**2.1 Repeated sentences (loops).** Sections that repeat one sentence many times:

| Bundle | Sections affected (of 35) | Worst case |
|---|---|---|
| Ashtavira | 10 | one sentence x137 in the business section |
| Kestrel | 9 | one sentence x69 in the promoters section |
| Bhuvanam | 8 | one sentence x38 in the management section |
| Oakvale | 10 | one sentence x25 in the MD&A section |
| Tavanvi | 8 | one sentence x23 in the objects section |

`loop_trimmed` is 0 in every section, so the drafter's loop detector did not fire on these repetitions. Repeats
are recurrent across bundles, so this is a decoding issue (greedy output with the frequency penalty), not a data
issue.

**2.2 Tables written as paragraphs.** Many table cells, such as "Amount to be deployed from the Net Proceeds 0
520.00 520.00", are stored as paragraph text, not table rows. The text is harder to read, and the cut-off check
counts these lines as truncated. The parser for the model's markdown tables needs a fix.

**2.3 Garbled figures and years.**
- "2,50,0,000/-(Rupees Two Crore Fifty Lakhs Only)" repeated about 24 times in the history section (Ashtavira). The
  amount is written with a stray comma and the repeat, so the number is malformed.
- "FY2100 to FY2105" in an industry section (found in the Ashtavira draft QC), a year range that does not fit an
  FY2025-26 document.
- The Bhuvanam sentence truncated at "Companies Act, 201" (see section 1).

**2.4 Objects of the issue.** The deployment table does not reconcile with the estimated amount of ₹4,230.00:
"Total deployment 1,860.00 520.00 2,586.00" against an estimate of 4,230.00, and "[●]" in the plant line. The
objects are a board decision, so they need checking against the source documents before any draft uses them.

**Count of cut-off lines per bundle (mostly tables as paragraphs, see 2.2):** Ashtavira 141, Bhuvanam 180, Kestrel
165, Oakvale 243, Tavanvi 171.

## 3. Status

- Grounding: four of five bundles have zero ungrounded values; Bhuvanam has one (truncated sentence).
- Draft quality: not client grade. Repeated-sentence loops in 8 to 10 sections per bundle, table-as-paragraph
  parsing, garbled figures.
- No drafting code has been changed for these defects yet. The next steps:
  1. Stop repetition (implemented in code, not yet re-run on the VM): `draft/writer.py` now sends
     `frequency_penalty` 0.3 on drafting calls (the value the drafting evaluations used) and runs every model draft
     through `trim_repeats`, which cuts a sentence that loops and keeps one copy. Sub-headings that looped are returned
     in `loop_trimmed`. The job 64 run had neither step, which is why `loop_trimmed` was 0. Tests:
     `tests/test_draft_loops.py`.
  2. Parse the model's markdown tables into table blocks.
  3. Validate amounts and years against the source (a year range must be a valid fiscal year; a total must reconcile).
  4. Re-run H5 on all five bundles and re-run this QC.

## 5. Job 65: rerun with the loop fix

Run: VM job 65 (`vm/h5.sbatch`), same model and bundles, with the drafting changes in section 3, step 1 (frequency
penalty 0.3, `trim_repeats` on every model draft, `loop_trimmed` reported). Outputs in `build/h5_job65/` (drafts and
blocks copied from the workspace folders). Job 64 outputs are kept on the VM as `~/sme/h5_job64`. Five bundles, 0 job
errors, 8.5 to 9.7 minutes each.

**Loops (fixed).** The worst repeated sentence is now x7 (was x137). The x6 and x7 repeats are in the risk factors,
which are written by rules (`draft/red_flags.py`), not by the model, so the loop trim does not touch them. Repeats of
x2 to x4 across sub-headings remain. `loop_trimmed` fires in 3 to 5 sub-headings per bundle (was 0).

**Grounding (not fixed in this run).** Ungrounded values: Ashtavira 6, Kestrel 3, Bhuvanam 0, Oakvale 0, Tavanvi 1
(job 64: 0, 0, 1, 0, 0). All of them are dates the model wrote that are not in the bundle files, for example "MSME
registration dated October 31, 2017" in Ashtavira. The verifier did not mask them because the model had put a blank
line inside the sentence ("...dated October 31," / "2017 issued by..."). Read as two paragraphs, the verifier never
sees the whole date. About 70 paragraphs across the five bundles end in a comma right after a date, and many of
them are split this way; some of the others are table headers. The parser now joins them (`draft/writer.py`, `_join_split_sentences`; test in `tests/test_draft_loops.py`). That change
is not in job 65, so it is not yet measured on the VM.

**Still open:** the rule-written risk-factor sentences repeat by design; table cells still stored as paragraphs (2.2);
garbled amounts and year ranges (2.3); the objects reconciliation (2.4).

## 6. Job 66: rerun with the sentence-join fix

Run: VM job 66 (`vm/h5.sbatch`), same model and bundles, with the loop fix and the sentence-join in
`draft/writer.py` (`_join_split_sentences`) as it stood at submission, i.e. joining a paragraph that ends in a comma.
Outputs in `build/h5_job66/`. Job 65 outputs are kept on the VM as `~/sme/h5_job65`. Five bundles, 0 job errors,
8.4 to 9.7 minutes each.

**Grounding.** Ungrounded values: Ashtavira 1, Kestrel 0, Bhuvanam 0, Oakvale 0, Tavanvi 0 (job 65: 6, 3, 0, 0, 1).
The one left is a page reference, "beginning on page no. 99", where the paragraph ends "...on page no." and "99."
starts the next block. The sentence-join rule covered a trailing comma only, so it did not join this pair. The rule now
also joins a paragraph ending in "page no.", a connector or "on"/"of"/"to"/"for"/"and"; test added. That change is not
in job 66, so it has not been measured on the VM.

**Loops.** Worst repeated sentence x7 (same as job 65; the x6 and x7 repeats are rule-written risk factors). `loop_trimmed`
fires in 3 to 5 sub-headings per bundle.

## 7. Job 71: final run

Run: VM job 71 (`vm/h5.sbatch`). Model: the base Qwen2.5-7B-Instruct with the A_qa_dpo LoRA adapter attached (vLLM
`--enable-lora`, served as `sme-drhp-7b`), not the merged copy. Jobs 69 and 70 failed before any drafting: 69 because
`peft` was missing from the vLLM environment, 70 because the merged model's save hit the VM's disk quota. The merged
model was deleted to free space; LoRA serving needs no copy. Merged and LoRA serving are the same model up to bf16
rounding. Five bundles, 0 job errors, 9 to 11 minutes each. Outputs in `build/h5_job71/`.

**Grounding (H5 criterion: zero invented figures): met in all five bundles.** Ungrounded values: 0 in every bundle
(job 67: 3; job 66: 1; job 65: 10).

**Loops.** Worst repeated sentence x7, the rule-written risk factors (`draft/red_flags.py`), not the model. `loop_trimmed`
fires in 3 to 5 sub-headings per bundle.

**Objects reconciliation (QC).** The new check flags 3 deployment rows that do not add up. Examples: a row with a
total and no year allocation ("- - 520"), and "Total deployment 1,860.00 + 520.00 = 2,380.00" against a total of
4,230. These are for a reviewer; the draft text is not changed.

**Open after this run:** tables written as plain text (2.2): the model writes them as paragraphs, and the fix needs a
change to the drafting prompt or training. Bundle page count (118 pages) and distinct financial profiles: kept as they
are at your request.

## 4. How to reproduce

```bash
# on the VM, after job 64 (outputs in ~/sme/h5_workspace/<pid>/)
# on the laptop
python vm/h5_measure.py build/h5_job64
python vm/h5_qc.py build/h5_job64
```
