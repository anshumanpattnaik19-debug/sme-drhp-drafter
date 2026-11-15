# Project log: client build, November 2026

A step-by-step record of the work in the session of 11 to 15 November 2026: what was done, the commands and
files involved, the results, what failed and how it was fixed, and what is still open. It is written for the
detailed report. Results marked *pending* were not yet available when this log was written.

Repository: `sme_drhp_drafter/`. Branch: `eval-harness-verifier` (local only; no GitHub remote yet).
Commits in this session: `d19331d` (client build). Earlier commits are listed in `NEXT_STEPS.md`.

---

## 1. Starting point

- Model: Qwen2.5-7B-Instruct, fine-tuned with QLoRA then DPO (`A_qa_dpo`), merged into bf16 weights
  (`~/models/A_qa_dpo_merged` on the course VM). Merge check: top-1 agreement 46/48 (0.958), gate 0.95.
- Serving smoke test passed through vLLM 0.10 (served name `sme-drhp-7b`).
- Evaluation, red team, judge, agentic RAG and the test sets are documented in `docs/MODEL_CARD.md`,
  `docs/RED_TEAM_LOG.md` and `NEXT_STEPS.md`. Agentic RAG was not used by default, because retrieval was weak.
- The user asked for a final, production-grade ("client grade") build: a local app, an installer, the five issuer
  bundles run end to end (H5), and an OCR route through a vision model.

## 2. Decisions and why

| Decision | Reason |
|---|---|
| The app works fully local; the drafting and vision models run on a server the user chooses | Several issuers' files are confidential, and the app must not send them to a third party |
| OCR by a vision LLM when configured, RapidOCR (offline) as the fallback | The user asked for LLM OCR for accuracy; RapidOCR keeps the app usable with no server |
| Installer per user (`PrivilegesRequired=lowest`) | No administrator rights needed; data stays in the user's profile |
| Bundles 2 to 5 share Ashtavira's financial model and vary identity | Building four distinct financial models was not feasible in this session; this is disclosed as a limit |
| Measure H5 against the bundle files, not only the fact store | The fact store misses values that are in the files; the first measurement overstated invented figures |
| Remove the merged drafting model from the VM before loading the vision model (planned) | The VM storage quota (32 GB soft, 35 GB hard) cannot hold both (see section 9) |

## 3. UI: production hardening

Files: `ui/src/components/ErrorBoundary.tsx` (new), `ui/src/main.tsx`, `ui/src/App.tsx`,
`ui/src/components/ProjectShell.tsx`, `ui/src/pages/Projects.tsx`, `ui/index.html`.

1. Added an error boundary around the app: an unexpected render error now shows a recoverable message.
2. Project cards are keyboard-accessible (role link, tab focus, Enter and Space).
3. The project shell is responsive: on narrow screens the navigation becomes a horizontal strip.
4. Added a "Skip to content" link and a `<main id="main">` landmark.
5. Page title and description set in `index.html`.
6. Settings dialog: added the vision-model section (server address, model name) and the matching types.
7. Build: `npm run build` passes (Vite, about 12 s).

## 4. Issuer bundles (H5 inputs)

### 4.1 Generator fixes (bundle 1 = Ashtavira)

- `bundles/pdfkit.py`: `Doc` had an attribute `title` that shadowed its `title()` method. Renamed the
  attribute to `doc_title`. This was the first real run error.
- Missing renderers written in `bundles/extra_docs.py`: director consents, Chartered Engineer capacity
  certificate, captioned plant photographs (generated illustrations, labelled synthetic), industry report (labelled
  illustrative market figures), and process flow chart (PNG).
- `bundles/scan.py`: makes a digital PDF look scanned (rasterise, grey, skew, noise, uneven light, JPEG, no text
  layer). Deterministic: the seed is the file name.
- `bundles/driver.py`: builds the full 42-file set from `issuer.build()`. The allotment-records renderer had been
  missed and was added. Output: 42 files, 118 pages, about 12 MB.

### 4.2 Bundles 2 to 5 (`bundles/variants.py`)

- Each variant is a retargeted copy of the generator. Names, identifiers, plots, bank, auditor, BRLM, legal
  counsel, research firm and people are replaced by a per-variant table.
- Replacement is done in one pass with a single regular expression, so a replacement is never replaced again.
- `bundles/check_leftovers.py` searches the text of built files for names of the source company. Result: no old
  names remain. "Sanand" remains in all four, because the estate is shared by design.
- Variant output: `bundles/out/{kestrel,bhuvanam,tavanvi,oakvale}_flexipak/`, 42 files each (ignored by git).

**Limits:** the four variants have the same financial figures; licence numbers are not retargeted; the page count
(118) is below the brief's 300 to 380 target.

## 5. H5 on the course VM

### 5.1 Setup

1. Installed `pymupdf`, `python-docx` and `openpyxl` into `~/venv-teacher` (fastapi, uvicorn and httpx were
   already there).
2. Copied the app packages (`serve`, `draft`, `extract`, `ingest`, `assemble`, `verify`, `rag`, `data`, `teacher`)
   to `~/sme/app/`.
3. Uploaded the five bundles to `~/sme/bundles/` (90 MB).
4. `vm/h5_run.py` drives the app in process through its own HTTP routes (FastAPI TestClient): create project,
   upload, process, draft all 35 sections, review. The settings point to the vLLM server.
5. `vm/h5.sbatch` starts `vllm serve` on port 8011 with the merged model, runs `h5_run.py`, then stops the server.

### 5.2 Runs

| Job | Outcome |
|---|---|
| 62 | Failed at import: `data/qa.py` needs `teacher/prompts.py`, which was not copied. Fixed by syncing `teacher/`. |
| 63 | Completed all five bundles, 0 job errors each. Measured in section 5.3. |
| 64 | Rerun with the fixes in section 6 (fresh workspace). Ashtavira complete (4,436 facts), Kestrel complete (2,070), Bhuvanam complete (2,071); Tavanvi and Oakvale *pending*. |

Job 63 facts per bundle: Ashtavira 4,440; Kestrel 2,118; Bhuvanam 2,119; Tavanvi 2,115; Oakvale 2,118.
Each bundle takes about 14 to 15 minutes end to end (upload, processing, drafting of 35 sections).

### 5.3 Measurement (job 63), `vm/h5_measure.py`

Method: each drafted value (figure, date, identifier, name, page reference) is checked against the text of the
bundle's own files, including OCR text from the VM (`blocks/`). A value is grounded when that text contains it.

| Bundle | Values checked | Ungrounded | Grounded |
|---|---|---|---|
| Ashtavira | 2,242 | 0 | 100.00% |
| Bhuvanam | 1,804 | 1 | 99.94% |
| Kestrel | 1,697 | 4 | 99.76% |
| Tavanvi | 1,799 | 1 | 99.94% |
| Oakvale | 1,666 | 2 | 99.88% |

The 8 remaining items: a "Page 2" template page reference in risk factors (copied from a running footer), and
date formats in the remuneration table ("March 31, 2023") that the model wrote and that the sources do not
contain. Both are fixed in section 6; job 64 measures the result (*pending*).

The app's own verifier, which checks only the fact store, reported 3 to 5 ungrounded values per bundle. Checking
against the bundle files showed the case number, the licence application number and a counterparty name are in
the sources but missing from the fact store. The measurement was therefore changed to use the bundle text.

## 6. Fixes made after job 63

1. **Running headers and footers** (`ingest/readers.py`, `strip_running_lines`): a short line that repeats exactly
   on at least 3 pages and at least 40% of the text pages is removed, as is a line that is only a page number.
   First version matched digits as well and removed body sentences ("Body paragraph 1" and "... 2" looked equal);
   tightened to exact matching. Test: `tests/test_ingest_clean.py`.
2. **Table cells in model drafts** (`draft/writer.py`): table cells are now masked like paragraphs. Previously a
   date in a table header was stored unmasked. Test: `tests/test_ingest_clean.py`.
3. **Whitespace-normalised measurement** (`vm/h5_measure.py`): a date split across a line break was counted as
   ungrounded.

## 7. Vision OCR route

- `ingest/readers.py`: `set_llm_ocr(cfg)`, `_ocr_llm(png)` (OpenAI-compatible `image_url` request with a base64 PNG
  of the page, temperature 0), and `_ocr_image_bytes` which uses the vision model when configured and falls back to
  RapidOCR per page on error, recording `last_ocr_error`.
- `serve/store.py`: new settings `ocr_backend` (auto, llm, rapidocr), `ocr_model_url`, `ocr_model_name`,
  `ocr_api_key`. The default OCR page limit is now 40 (was 12).
- `serve/app.py`: `_ocr_cfg(settings)` applied before each processing run; `SettingsPatch` accepts the new fields;
  `/api/health` reports `ocr_error`.
- Tests: `tests/test_ocr_llm.py` (3): the image reaches the endpoint as a PNG data URL; the answer is used; an
  unreachable endpoint falls back. Full suite: 63 passing at that point; 66 after section 6.
- End-to-end check through the API against a stub endpoint on port 8800: the scanned certificate was processed,
  and its OCR text came from the stub. The test project was then deleted.
- Not tested: a real vision model. The stub only checks the route.

## 8. UI upload smoke test (browser)

1. Local app at `http://localhost:8765` (preview server).
2. Created project "Kestrel Flexipak Limited" through the New project dialog.
3. The Documents page has a hidden file input. Attached all 42 files to it from JavaScript: a `DataTransfer` built
   from files fetched from a local file server (`scratchpad/cors_serve.py`, port 8790, CORS enabled), then a
   `change` event. The app's own handler accepted them.
4. Result: 42 uploaded; processing started by itself ("Read and extract automatically after upload").
5. Processing result (with the OCR limit of 12 pages per file): 42 processed, 0 errors, 2,170 facts, 118 pages,
   OCR on 29 pages, 12 pages left unread. After the limit was raised to 40 this changes; the scanned statements
   now read in full.
6. Files with no facts: `00_Document_Index.xlsx`, the process-flow PNG, the fire NOC scan and the plant
   photographs. Expected for the index and the images; the fire NOC scan is an open question.
7. Screenshot confirmed the project page and file list.

## 9. Docker

1. Installed Docker Desktop 4.99.0 with `winget install -e --id Docker.DockerDesktop`. The installer asked for
   administrator approval (UAC). The user approved the install before it ran.
2. WSL was not installed. Ran `wsl --install --no-distribution` with administrator approval; WSL 2 is the default.
3. Started Docker Desktop; the engine came up after about 90 seconds. Client 29.9.3.
4. `docker/Dockerfile.app` rewritten as a two-stage build: a Node stage builds the UI, and a Python 3.12 slim stage
   installs `requirements-app.txt` and copies only the app packages (`serve`, `draft`, `extract`, `ingest`,
   `assemble`, `verify`, `rag`, `data`, `teacher`) and `ui/dist`.
5. `.dockerignore` excludes the training data, the bundles, the workspace and the UI sources.
6. Build problems fixed on the way:
   - The first run failed: `teacher` package missing (`data/qa.py` imports it). Added.
   - OCR failed to import: `libxcb.so.1` missing. Added `libgl1`, `libglib2.0-0`, `libxcb1` through apt.
   - The mount paths were rewritten by Git Bash; fixed with `MSYS_NO_PATHCONV=1`.
7. Result: image `drhp-studio:latest`, 1.04 GB. Smoke test: `/api/health` OK, UI returned HTTP 200, project create
   and list work.
8. Offline check: `vm/offline_check.py` run with `docker run --network none`: OCR available, a scanned certificate
   processed (1 page, 1 fact). The app works with no network.
9. `docker compose -f docker/docker-compose.yml config`: valid (exit 0). **Not run end to end**, because it needs
   an NVIDIA GPU host for the vLLM service.

## 10. Installer (Windows)

1. Frozen app with PyInstaller 6.20.0 (`desktop/launcher.py`, one folder). Excluded packages: torch, transformers,
   tensorflow, matplotlib, scipy, sklearn, pandas, IPython, tkinter. The first builds pulled in those packages
   through `collect-submodules data`, so the data package was dropped from collection.
2. Bug found: `shapely` had been excluded, but RapidOCR needs it. Health reported `ocr_available: false`. The
   diagnostic (`ocr_error` in `/api/health`, added for this) showed `ModuleNotFoundError: No module named 'shapely'`.
   Fixed by removing that exclusion. Health then reported OCR available.
3. `serve/app.py`: the UI path can be set with `DRHP_UI_DIST`; the launcher sets it.
4. Inno Setup 6.7.3 installed per user with `winget install -e --id JRSoftware.InnoSetup --scope user` (no
   administrator approval needed). Compiler: `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`.
5. `desktop/DRHPStudio.iss`: per-user install to `%LOCALAPPDATA%\Programs\DRHP Studio`, Start menu entries, an
   optional desktop shortcut, the app as the run-after-install action, and an uninstaller. The AppId is a generated
   GUID.
6. Compiled: `build/installer/DRHPStudio-Setup-1.0.0.exe`, 200.6 MB (compile about 5 minutes).
7. Silent install test: `DRHPStudio-Setup-1.0.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS`. Passing a
   scratch `/DIR` through Git Bash did not work (the install went to the default location). The test ran the
   installed copy with `DRHP_PORT=8779`: health OK with OCR available, UI HTTP 200. The uninstaller removed the
   program files; the data folder `%LOCALAPPDATA%\DRHP Studio` is kept, by design.
8. Test that failed first and was corrected: PowerShell 5.1's `Start-Process` has no `-Environment` parameter, so
   the first attempt never started the app. The uninstall ran as the cleanup step, so nothing was left behind.

## 11. Commit

- `d19331d` "Client build: local app, LLM OCR route, installer, issuer bundles 2-5, H5 fixes": 33 files,
  1,594 insertions, 20 deletions.
- Generated outputs are ignored (`build/`, `bundles/out/`, `bundles/_upload/`): the installer, the frozen app, the
  generated bundles and the VM outputs are not in git.
- Attribution line: `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
- Git reported CRLF conversion warnings on Windows; no content change.

## 12. Documents written

| File | Contents |
|---|---|
| `README.md` | install, run from source, Docker, settings, data locations, tests, limits |
| `docs/INSTALLER.md` | build the frozen app and the installer; test steps |
| `docs/BUNDLES.md` | the five bundles, what is shared and what differs, regeneration commands |
| `docs/PROJECT_LOG_2026-11.md` | this log |

## 13. Test status

- `pytest tests`: 66 passed (last full run, after section 6).
- `npm run build` (UI): passes.
- `docker compose config`: valid.
- H5 measurement: job 63 measured (section 5.3); job 64 *pending*.

## 14. Open items

1. **H5 job 64**: Tavanvi and Oakvale still running at the last check. Then run `vm/h5_measure.py` on the job 64
   outputs and write `docs/H5_RESULTS.md`. H5 passes only at zero ungrounded values.
2. **Vision model**: not chosen. Recommended Qwen2.5-VL-7B-Instruct on the VM. Needs 16.6 GB free storage. The
   plan: remove the merged drafting model (regenerable from the saved adapter and base with `vm/merge_adapter.py`),
   download the model, run base OCR on the scanned pages against the known text the generator writes before
   scanning, and report the character error rate before any training decision.
3. **GitHub**: no remote is configured. Needs the repository URL to push `eval-harness-verifier`.
4. **Docker compose**: needs a GPU host to run end to end.
5. **Fire NOC scan** (`05_Fire_NOC_Expired.jpg`) produced no facts in the UI smoke test. To check the OCR output for
   that file.
6. **Bundle page count**: 118 pages against the 300 to 380 target in the brief.
7. **Distinct financial profiles** for bundles 2 to 5: not done (shared model).

## 14a. Status after the final round (15 Nov 2026)

Done: the H5 run on all five bundles passes the grounding criterion (zero ungrounded values, job 71, see
`docs/H5_RESULTS.md` section 7). Repetition loops are fixed (worst x7, rule-written risk factors). The OCR error-rate
test is recorded in `docs/OCR_EVAL.md`: the base vision model has 12.8% character error and recovers 174 of 186 numbers,
against 55.8% for the offline RapidOCR, so no fine-tuning is needed yet. Also done: the verifier checks fiscal years,
OCR dates without spaces are read, a split sentence is one paragraph, the QC checks that deployment rows add up.

Open items, updated:
1. **Vision model**: Qwen2.5-VL-7B-Instruct is on the VM (16 GB). Its error rates are in `docs/OCR_EVAL.md`.
2. **GitHub**: the remote is configured (`origin`, branch `eval-harness-verifier`). See the commit for the push status.
3. **Docker compose**: needs a GPU host with Docker. The VM has no Docker, and the laptop has no NVIDIA GPU.
4. **Fire NOC scan**: OCR reads the certificate, but the dates ran together ("21September2023"). The date rules now
   accept that form. Not yet checked in a full extraction run.
5. **Bundle page count (118 pages) and distinct financial profiles**: kept as they are, at the user's decision.
6. **Tables written as plain text in drafts**: open. The fix is a change to the drafting prompt or training.
7. **Objects reconciliation**: the QC flags rows that do not add up. The figures need checking against the board
   resolution and the source documents before any draft uses them.
8. **Merged drafting model**: deleted from the VM to free storage. Not needed: LoRA serving runs the same model.

## 15. Reproduce

```bash
# bundles
python bundles/variants.py
python bundles/check_leftovers.py bundles/out/kestrel_flexipak Ashtavira Desai Bhatt Kalindi Arthaveda Meridian

# tests and UI
python -m pytest tests -q
cd ui && npm ci && npm run build

# app locally
python -m uvicorn serve.app:app --host 127.0.0.1 --port 8765

# Docker
docker build -f docker/Dockerfile.app -t drhp-studio .
docker run --rm --network none -v "$(pwd -W)/bundles/out/kestrel_flexipak:/data/bundle:ro" \
  -v "$(pwd -W)/vm:/app/vm:ro" drhp-studio python /app/vm/offline_check.py

# installer
python -m PyInstaller --noconfirm --onedir --console --name DRHPStudio --paths . \
  --add-data "ui/dist;ui/dist" --add-data "verify/vocab.txt;verify" \
  --collect-data rapidocr_onnxruntime --collect-submodules serve --collect-submodules draft \
  --collect-submodules extract --collect-submodules ingest --collect-submodules assemble \
  --collect-submodules verify --collect-submodules rag \
  --exclude-module torch --exclude-module transformers --exclude-module tensorflow \
  --exclude-module matplotlib --exclude-module scipy --exclude-module sklearn \
  --exclude-module pandas --exclude-module IPython --exclude-module tkinter \
  --distpath build/pyi/dist --workpath build/pyi/work --specpath build/pyi desktop/launcher.py
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\DRHPStudio.iss

# VM: H5
sbatch vm/h5.sbatch          # logs: ~/sme/logs/h5-bundles-<job>.out
python vm/h5_measure.py build/h5
```
