#!/usr/bin/env bash
# A_qa3 (SFT only) on the full test_v2 set (drafting, extraction, Q&A): the regression check for a possible swap.
#SBATCH --job-name=qa3-v2
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
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$HOME/checkpoints/A_qa3/adapter" --test trainset/out/test_v2.jsonl --out "$HOME/checkpoints/A_qa3/v2" --name A_qa3
echo SFT_V2_DONE
