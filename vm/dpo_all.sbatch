#!/usr/bin/env bash
# DPO against looping for run A_qa, in one job (the VM allows one running and one waiting job per learner):
#   1. pairs   A_qa drafts 400 training prompts; looped or capped drafts become 'rejected'   (vLLM: ~/venv-teacher)
#   2. train   DPO on top of A_qa, reference = the starting adapter                          (QLoRA: ~/venv)
#   3. predict A_qa_dpo on test_v2.jsonl, same decoding as A_qa                              (vLLM: ~/venv-teacher)
# Submit from ~/sme:   sbatch vm/dpo_all.sbatch
#SBATCH --job-name=dpo-all
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
DPO="$HOME/checkpoints/A_qa_dpo"
SRC="$HOME/checkpoints/A_qa-51/adapter"
mkdir -p "$DPO"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

echo "== 1. pairs"
"$HOME/venv-teacher/bin/python" vm/dpo_pairs.py --adapter "$SRC" --train trainset/out/train_v2.jsonl --out "$DPO/pairs.jsonl"

echo "== 2. train"
"$HOME/venv/bin/python" vm/dpo_train.py --src-adapter "$SRC" --pairs "$DPO/pairs.jsonl" --out "$DPO/run"

echo "== 3. predict"
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$DPO/run/adapter" --test trainset/out/test_v2.jsonl \
  --out "$DPO" --name A_qa_dpo
echo "DPO_ALL_DONE"
