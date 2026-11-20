"""Host the app on a free Hugging Face Docker Space behind a shared password (docs/HOSTING.md).

    python -m serve.space deploy      # create or update the Space, set its secrets, upload the code
    python -m serve.space status      # build or run state, and the app's address

HF_TOKEN, RUNPOD_API_KEY and APP_PASSWORD come from the environment or .runpod.env. They become Space secrets; they
are never written to a file, uploaded or printed. The model URL comes from build/runpod_endpoint.json.
"""
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import sys
from pathlib import Path

from serve.runpod import ROOT, key, load_state

STAGE = ROOT / "build" / "space"
CODE = ["serve", "draft", "extract", "ingest", "assemble", "verify", "rag", "data", "teacher", "rai"]
UI = ["ui/src", "ui/public", "ui/index.html", "ui/package.json", "ui/package-lock.json", "ui/postcss.config.js",
      "ui/tailwind.config.js", "ui/tsconfig.json", "ui/vite.config.ts"]
README = """---
title: DRHP Copilot
emoji: 📄
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: SME DRHP drafting assistant (password protected)
---

# DRHP Copilot

A research prototype that drafts sections of an SME Draft Red Herring Prospectus from an issuer's own files, for review
by the lead manager and legal counsel. Access needs the shared password. Drafts are not filed, signed off or sent
without a person checking them against the issuer's documents.

Files uploaded here are kept only until the Space restarts.
"""


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", "out", "node_modules", "dist", "runpod.py", "space.py",
                                 "corpus_*.jsonl")
    for d in CODE:
        shutil.copytree(ROOT / d, STAGE / d, ignore=skip)
    for p in UI:
        src = ROOT / p
        (shutil.copytree(src, STAGE / p, ignore=skip) if src.is_dir() else
         (STAGE / p).parent.mkdir(parents=True, exist_ok=True) or shutil.copy2(src, STAGE / p))
    shutil.copy2(ROOT / "requirements-app.txt", STAGE / "requirements-app.txt")
    shutil.copy2(ROOT / "docker" / "Dockerfile.space", STAGE / "Dockerfile")
    (STAGE / "README.md").write_text(README, encoding="utf-8")
    leaked = [p for p in STAGE.rglob("*") if p.is_file() and (p.name.startswith(".env") or p.name == ".runpod.env")]
    if leaked:
        sys.exit(f"refusing to upload secret files: {leaked}")
    return sum(1 for p in STAGE.rglob("*") if p.is_file())


def deploy(args):
    from huggingface_hub import HfApi
    url = load_state().get("model_url")
    if not url:
        sys.exit("no RunPod endpoint: run `python -m serve.runpod create` first")
    api = HfApi(token=key("HF_TOKEN"))
    repo = args.name if "/" in args.name else f"{api.whoami()['name']}/{args.name}"
    api.create_repo(repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    for name, value in (("RUNPOD_API_KEY", key("RUNPOD_API_KEY")), ("APP_PASSWORD", key("APP_PASSWORD")),
                        ("APP_SESSION_SECRET", secrets.token_hex(32))):
        api.add_space_secret(repo, name, value)
    api.add_space_variable(repo, "DRHP_MODEL_URL", url)
    api.add_space_variable(repo, "DRHP_MODEL_NAME", "sme-drhp-7b")
    n = stage()
    api.upload_folder(repo_id=repo, repo_type="space", folder_path=str(STAGE), commit_message="DRHP Studio",
                      delete_patterns=["*"])
    host = repo.replace("/", "-").replace("_", "-").lower()
    print(f"Space {repo}: {n} files uploaded; secrets RUNPOD_API_KEY, APP_PASSWORD, APP_SESSION_SECRET set")
    print(f"page: https://huggingface.co/spaces/{repo}\napp:  https://{host}.hf.space   (builds for a few minutes)")


def status(args):
    from huggingface_hub import HfApi
    api = HfApi(token=key("HF_TOKEN"))
    repo = args.name if "/" in args.name else f"{api.whoami()['name']}/{args.name}"
    rt = api.get_space_runtime(repo)
    print(f"{repo}: {rt.stage} | hardware {rt.hardware} | https://{repo.replace('/', '-').lower()}.hf.space")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m serve.space", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("deploy", "status"):
        p = sub.add_parser(c)
        p.add_argument("--name", default="drhp-studio", help="Space name, or user/name")
    args = ap.parse_args(argv)
    return {"deploy": deploy, "status": status}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
