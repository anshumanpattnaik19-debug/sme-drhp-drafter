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
  1. Stop repetition: apply a repeat penalty or a stop-on-repeat rule in the drafting call, and make the loop trim
     apply to whole repeated sentences, not only to repeated tokens.
  2. Parse the model's markdown tables into table blocks.
  3. Validate amounts and years against the source (a year range must be a valid fiscal year; a total must reconcile).
  4. Re-run H5 on all five bundles and re-run this QC.

## 4. How to reproduce

```bash
# on the VM, after job 64 (outputs in ~/sme/h5_workspace/<pid>/)
# on the laptop
python vm/h5_measure.py build/h5_job64
python vm/h5_qc.py build/h5_job64
```
