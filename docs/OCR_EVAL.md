# OCR error-rate test (vision model vs offline RapidOCR)

Question: is the base vision model good enough for scanned issuer files, or does it need fine-tuning first? The plan
(PROJECT_LOG section 14, item 2) was to measure the base model before any training decision.

## Test set

Built by `vm/ocr_eval_make_set.py` from the Kestrel bundle (`bundles/out/kestrel_flexipak`):

- 8 pages of the two scanned audited statements (FY 2024-25 and FY 2023-24, first four pages of each), rendered at
  200 dpi, the same as the app's OCR.
- 3 scanned certificates (incorporation, factory licence, GPCB consent).
- Ground truth: the digital text of the same page, from the bundle's `_work` folder (the pre-scan PDF). The scan adds
  noise to the image, not to the text, so the digital text is the true content.

11 pages, 186 numbers, about 33,000 characters of truth.

## Engines

- **Vision model:** Qwen2.5-VL-7B-Instruct, served by vLLM 0.10 on the course VM (`vm/ocr_eval.sbatch`, job 68), with
  the app's OCR prompt (`ingest/readers.py`, `OCR_PROMPT`) and temperature 0.
- **RapidOCR:** the offline engine the app falls back to, run on the laptop through `ingest/readers.py`.

## Scoring

`vm/ocr_eval_score.py`. Whitespace and table bars are removed on both sides, so layout is not scored.

- **Character error rate (CER):** edit distance divided by the true length. Sensitive to reading order.
- **Word recall:** share of the true words (multiset) that the OCR text contains, whatever their order.
- **Numeric recall:** share of the true numbers recovered, counted as a multiset.

## Results

| Engine | CER | Word recall | Numeric recall |
|---|---|---|---|
| Qwen2.5-VL-7B (base) | 12.8% | 96.4% | 93.5% (174 of 186) |
| RapidOCR (offline) | 55.8% | 11.3% | 71.0% (132 of 186) |

Per page, the vision model's CER ranges from 4.4% (large statement pages) to 27% (certificates). The worst pages are
the two cover pages (about 430 characters each, CER 82%): the truth includes a running header ("SYNTHETIC TEST
DOCUMENT ... Page 1") that the model did not transcribe. The word recall on those pages is still 96%.

RapidOCR's low word recall is mostly spacing: it runs words together ("FIRESAFETYCERTIFICATE", "PlotNo.214-216"),
which breaks date and label matching. Its numbers survive better than its words.

## What this means

- The base vision model reads the scanned pages far better than RapidOCR, and it is the right default for scanned
  issuer files. The app already uses it through the vision-model setting.
- It still misses about 1 number in 15 (12 of 186). Figures in a DRHP cannot be taken from OCR unchecked, so the
  verifier (which masks any figure not found in the inputs) and a reviewer remain necessary. A missed figure is
  masked or absent; it is not replaced with a wrong one, but the verifier cannot catch a figure it mis-reads as another
  figure that is also in the inputs.
- **Fine-tuning decision:** not justified by this test. The base model's errors are mostly a missed running header and
  a small share of misread numbers. Fine-tuning would need a labelled set of scanned issuer pages with the true text,
  which is the next step only if the miss rate must fall further. Recommended first: a larger test (more bundles, the
  Ashtavira and Bhuvanam scans) to confirm 13% CER and 6 to 7% numeric misses hold across layouts.

## Reproduce

```bash
python vm/ocr_eval_make_set.py bundles/out/kestrel_flexipak build/ocr_eval      # laptop
scp -r build/ocr_eval/images build/ocr_eval/truth build/ocr_eval/manifest.json tracka:sme/ocr_eval/   # VM
sbatch vm/ocr_eval.sbatch                                                       # VM, job writes transcripts_qwen_vl.json
scp tracka:sme/ocr_eval/transcripts_qwen_vl.json build/ocr_eval/                 # laptop
python vm/ocr_eval_score.py build/ocr_eval build/ocr_eval/transcripts_qwen_vl.json
```
