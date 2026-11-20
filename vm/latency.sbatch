#!/usr/bin/env bash
# Batch-1 latency without prefix caching (real prefills): base + adapter (bf16, as RunPod serves it) and the AWQ export.
#SBATCH --job-name=latency
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:45:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
Q="$HOME/checkpoints/quant"
"$HOME/venv-teacher/bin/python" vm/quant_eval.py --model BASE --adapter "$HOME/checkpoints/A_qa3_dpo3/run/adapter" --name bf16_lora --out "$Q" --latency-only
"$HOME/venv-teacher/bin/python" vm/quant_eval.py --model "$HOME/models/A_qa3_dpo3_awq" --name awq --out "$Q" --latency-only
echo "LATENCY_DONE"
