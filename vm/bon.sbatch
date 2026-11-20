#!/usr/bin/env bash
# Best-of-3 drafts for the new, the shipped and the base model on the app-format prompts.
#SBATCH --job-name=bon
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
"$HOME/venv-teacher/bin/python" vm/predict_bon.py --test trainset/out/test_app.jsonl --out "$HOME/checkpoints/bon" --with-base \
  --adapter A_qa3_dpo=$HOME/checkpoints/A_qa3_dpo/run/adapter --adapter A_qa_dpo=$HOME/checkpoints/A_qa_dpo/run/adapter
