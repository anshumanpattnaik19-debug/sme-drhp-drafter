# DRHP Copilot: release notes (15 November 2026)

## What is delivered

- **The app:** a local web app (FastAPI backend, React UI) that reads an issuer's files (Word, Excel, PDF, scanned pages,
  images), extracts facts, and drafts the sub-sections of an SME Draft Red Herring Prospectus. Every figure is checked
  against the inputs; a figure the inputs do not support is masked as `[●]`.
- **Windows installer:** `DRHPStudio-Setup-1.0.0.exe` (101 MB). It installs for the current user, with no administrator
  rights, and needs no internet connection for the offline drafter and OCR.
- **Docker image:** `docker/Dockerfile.app`, which runs the same app on port 8765.
- **Drafting model:** Qwen2.5-7B-Instruct with the A_qa_dpo LoRA adapter. It runs on a GPU server (the course VM with
  vLLM) and is configured in Settings. The adapter is published separately (see below).
- **Vision model (optional):** Qwen2.5-VL-7B-Instruct for OCR of scanned pages, configured in Settings. Without it,
  RapidOCR reads the pages on the CPU.

## What was verified

| Check | Result | Where |
|---|---|---|
| Five issuer bundles, end to end through the app | Zero ungrounded values in all five bundles (final run, see H5_RESULTS.md section 9) | `docs/H5_RESULTS.md` |
| Repetition loops in drafts | Worst repeated sentence x7 (rule-written risk-factor wording); the loop trim cuts model loops | `docs/H5_RESULTS.md` |
| OCR error rate (vision model) | 12.8% character error, 174 of 186 numbers recovered; RapidOCR 55.8% | `docs/OCR_EVAL.md` |
| Installer on a Windows laptop | Installs silently; the app starts and passes the smoke test | `docs/INSTALLER.md` |
| Docker image | Starts; the smoke test passes with the offline drafter | `docs/DOCKER_TEST.md` |
| Tests | 86 pass | `tests/` |

## What is not verified

- **The drafting model inside Docker or on the laptop.** The model needs a GPU server. The laptop has a 4 GB AMD
  graphics card, and the course VM doesn't accept connections from the laptop, so the Docker and installed app were
  tested with the offline drafter only.
- **Tables written as plain text by the model.** Runs of such rows now become tables, but headers stay as text.
- **Objects figures.** Model-written deployment rows that don't add up are masked, and the QC flags them, but the source
  schedule must be checked by a reviewer before any draft is used.
- **The OCR labels of scanned facts.** OCR often runs words together ("Validupto"), so some labels read poorly. The values
  are correct.

## Decisions kept as they are

- The bundles stay at 118 pages, and the financial profiles are shared across bundles 2 to 5 (test-set limits, not app
  limits).

## Where the model lives

- The adapter is about 154 MB and is published as a private Hugging Face repository (pending the laptop login).
- The base model is Qwen2.5-7B-Instruct, which the adapter loads from the Hugging Face Hub.

## Run it

Installed app: run `DRHP Copilot` from the Start menu. It opens `http://127.0.0.1:8765` in the browser.

Docker:

```bash
docker build -f docker/Dockerfile.app -t drhp-studio .
docker run -p 8765:8765 drhp-studio
```

Source:

```bash
pip install -r requirements-app.txt
cd ui && npm ci && npm run build && cd ..
python -m uvicorn serve.app:app --host 127.0.0.1 --port 8765
```

Drafting model: in Settings, set the model address and name (for example `sme-drhp-7b`). Without a model server, the app
drafts with the offline drafter.

## v1.2 (22 Nov 2026)

Tag `v1.2` (commit 9312f6e): guard, extraction and drafting fixes from three hosted data-room tests (docs/HOSTING.md, FAILURE_LOG.md items 39 to 41),
drafting penalty 0.1, unit check, 301 tests. Same adapter as v1.1 (A_qa3_dpo3). Live on the hosted app as `/healthz` commit `9312f6e51133`, guard build `65b3c20d423e`.
