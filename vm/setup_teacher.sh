#!/usr/bin/env bash
# Course VM (upgrad-l40s-vm03, driver 565 / CUDA 12.6): teacher environment and model for the Q&A pairs (stage 2c).
# Runs on the login node (CPU and network only, no GPU hours). vLLM 0.32 has no CUDA 12.6 build, so the teacher runs
# on vLLM 0.10.0+cu126 in its own venv; the course venv (~/venv, torch 2.14+cu126) is left untouched.
#   nohup bash ~/sme/vm/setup_teacher.sh > ~/sme/logs/setup_teacher.log 2>&1 &
set -Eeuo pipefail
source "$HOME/.tracka_environment"
export UV_CACHE_DIR=/tmp/uv-$USER          # install cache outside the 32 GiB quota
export PIP_CACHE_DIR=/tmp/pip-$USER
mkdir -p "$HOME/sme/logs" "$HOME/models" "$HF_HOME"

echo "[$(date +%T)] teacher venv"
if [ ! -x "$HOME/venv-teacher/bin/python" ]; then
  python3 -m venv "$HOME/venv-teacher"
fi
source "$HOME/venv-teacher/bin/activate"
pip install -q --upgrade pip uv
uv pip install "https://github.com/vllm-project/vllm/releases/download/v0.10.0/vllm-0.10.0+cu126-cp38-abi3-manylinux1_x86_64.whl" \
  "httpx>=0.27" --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
python -c "import vllm, torch; print('vllm', vllm.__version__, '| torch', torch.__version__, '| cuda', torch.version.cuda)"

echo "[$(date +%T)] teacher model"
hf download Qwen/Qwen3-32B-AWQ --local-dir "$HOME/models/Qwen3-32B-AWQ" 2>&1 | tail -2 || \
  huggingface-cli download Qwen/Qwen3-32B-AWQ --local-dir "$HOME/models/Qwen3-32B-AWQ" 2>&1 | tail -2
du -sh "$HOME/models/Qwen3-32B-AWQ"
quota -s | tail -1
rm -rf "$UV_CACHE_DIR" "$PIP_CACHE_DIR"
echo "[$(date +%T)] setup done"
