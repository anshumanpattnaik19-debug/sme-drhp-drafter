# Installing DRHP Copilot on Windows

> The app is called DRHP Copilot (renamed from DRHP Studio on 19 Nov 2026). The data folder keeps the old name, `DRHP Studio`, so projects of earlier installs are found without a move.

DRHP Copilot runs entirely on the user's computer. Issuer files are read, OCR'd and indexed locally, and stored in
`%LOCALAPPDATA%\DRHP Studio\workspace`. The installer does not need administrator rights.

## What the installer contains

- The DRHP Copilot backend (FastAPI) and the built React UI.
- Python runtime and libraries: PyMuPDF, python-docx, openpyxl, and RapidOCR (OCR models included, no download).
- A launcher that starts the app on `http://127.0.0.1:8765` and opens it in the default browser.

## What the installer does not contain

The drafting model and the vision model are large (about 15 GB for the 7B model in bf16). They are configured
separately in **Settings**:

- **Drafting model:** an OpenAI-compatible server, for example vLLM or llama.cpp, at the address set in Settings.
  Without one, the app drafts with its offline drafter.
- **Vision model for OCR (optional):** a vision-capable model such as Qwen2.5-VL-7B-Instruct on an
  OpenAI-compatible server. When set, every scanned page goes to it for transcription. When empty, RapidOCR reads
  the pages offline on the CPU.

## Build the installer (developer)

1. Install Inno Setup 6 (per user: `winget install -e --id JRSoftware.InnoSetup --scope user`).
2. From the repository root, freeze the app:

   ```bash
   python -m PyInstaller --noconfirm --onedir --console --name DRHPStudio --paths . \
     --add-data "ui/dist;ui/dist" --add-data "verify/vocab.txt;verify" \
     --collect-data rapidocr_onnxruntime --collect-submodules serve --collect-submodules draft \
     --collect-submodules extract --collect-submodules ingest --collect-submodules assemble \
     --collect-submodules verify --collect-submodules rag \
     --exclude-module torch --exclude-module transformers --exclude-module tensorflow \
     --exclude-module shapely --exclude-module matplotlib --exclude-module scipy \
     --exclude-module sklearn --exclude-module pandas --exclude-module IPython --exclude-module tkinter \
     --distpath build/pyi/dist --workpath build/pyi/work --specpath build/pyi desktop/launcher.py
   ```

3. Compile the installer:

   ```bash
   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\DRHPStudio.iss
   ```

   The output is `build/installer/DRHPStudio-Setup-1.0.0.exe`.

## Test the frozen app before shipping

- Run `build\pyi\dist\DRHPStudio\DRHPStudio.exe`; the browser opens at `http://127.0.0.1:8765`.
- Upload a scanned PDF and confirm pages are read (OCR) with no network connection.
- Uninstall from Windows Settings and confirm the data folder under `%LOCALAPPDATA%\DRHP Studio` is kept.

## Status

Verified on 15 November 2026 on the developer's Windows laptop (AMD graphics, 15 GB RAM):

- The frozen build (`DRHPStudio.exe`, 305 MB) starts and answers `/api/health` with OCR available.
- The installer (`DRHPStudio-Setup-1.0.0.exe`, 101 MB) installs silently for the current user, with no administrator
  rights, to `%LOCALAPPDATA%\Programs\DRHP Studio`.
- The installed app passes the smoke test in `vm/docker_smoke.py`: six issuer files uploaded and processed (739 facts),
  and a section drafted with the offline drafter.

Build notes from this run:

- PyInstaller resolves `--add-data` paths from the spec folder, so the build uses absolute paths.
- The `rag` package imports `sentence_transformers` (optional dense retrieval, inside a try block). Collecting `rag`
  pulls in torch, torchvision and datasets unless those modules are excluded. The build excludes them; the app falls
  back to its lexical retrieval.
- A running copy of the app locks its files, so the old frozen folder cannot be deleted while it runs. Stop the app
  before rebuilding.
