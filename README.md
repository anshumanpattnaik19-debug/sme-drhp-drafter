# DRHP Studio

Drafts SME offer documents (DRHP sub-sections for BSE SME) from an issuer's own files. Every figure keeps its source,
and a figure the files do not support is masked as `[●]` rather than stated.

DRHP Studio runs on the user's computer. Issuer files are read, OCR'd and indexed locally, and stored in the user's
data folder. Several issuers can be kept in one installation: each project has its own folder.

## Install (Windows)

Run `DRHPStudio-Setup-<version>.exe`. The installer does not need administrator rights and installs for the current
user. It contains the app, the built UI, the Python runtime and the OCR engine (models included). Start it from the
Start menu or the desktop shortcut; the app opens in the browser at `http://127.0.0.1:8765`.

The drafting model and the vision model are large and are configured in **Settings** (see below). The app works
without them: sections are drafted with the offline drafter.

Build the installer yourself: [docs/INSTALLER.md](docs/INSTALLER.md).

## Run from source

```bash
pip install -r requirements-app.txt
cd ui && npm ci && npm run build && cd ..
python -m uvicorn serve.app:app --host 127.0.0.1 --port 8765
```

Docker: `docker build -f docker/Dockerfile.app -t drhp-studio .` then `docker run -p 8765:8765 drhp-studio`.
`docker/docker-compose.yml` runs the app with a vLLM model server (needs an NVIDIA GPU).

## Configuration (Settings)

| Setting | What it does | Default |
|---|---|---|
| Drafting model address and name | OpenAI-compatible server used to draft and answer questions (for example vLLM serving the fine-tuned model) | none: offline drafter |
| OCR | Reads scanned PDFs and images | on (RapidOCR, offline) |
| OCR page limit per file | Pages beyond the limit are flagged, not read | 40 |
| Vision model (server address, model name) | If set, each scanned page is sent to this vision model for transcription; RapidOCR is the fallback | empty |

No file leaves the computer unless a server address is set in Settings, and then only to that address.

## Where data is kept

- Windows installer: `%LOCALAPPDATA%\DRHP Studio\workspace\<project>\` (files, extracted facts, drafts).
- Source run: `workspace/` in the repository, or the folder in `DRHP_WORKSPACE`.

Uninstalling the app keeps this folder.

## Tests

```bash
python -m pytest tests -q
```

## Evaluation and status

- The model card (training data, test results, known failure modes): [docs/MODEL_CARD.md](docs/MODEL_CARD.md).
- Red-team results: [docs/RED_TEAM_LOG.md](docs/RED_TEAM_LOG.md).
- Issuer bundles for the end-to-end test (five companies, 42 files each): [docs/BUNDLES.md](docs/BUNDLES.md).

## Limits

- Drafts are a first draft for the BRLM and legal counsel. They are not for filing without a person checking them
  against the issuer's documents.
- Figures and identifiers in the issuer bundles are synthetic; the four variant bundles share one financial model.
- The vision model for OCR is not yet chosen; RapidOCR is the tested default.
