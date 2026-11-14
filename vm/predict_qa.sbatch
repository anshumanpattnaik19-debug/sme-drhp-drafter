#!/usr/bin/env bash
# Predictions for run A_qa and the base model on test_v2.jsonl (about 20 minutes on an L40S).
# Submit from ~/sme:   sbatch vm/predict_qa.sbatch
#SBATCH --job-name=qa-predict
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python vm/predict_qa.py --adapter "$HOME/checkpoints/A_qa-51/adapter" \
  --test trainset/out/test_v2.jsonl --out "$HOME/checkpoints/A_qa-51"
