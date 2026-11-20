#!/usr/bin/env bash
# Four drafts per training prompt (app format) from A_qa3, for the on-policy preference pairs (data/onpolicy_pairs.py).
#SBATCH --job-name=op-sample
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
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
"$HOME/venv-teacher/bin/python" vm/predict_bon.py --test trainset/out/train_app.jsonl --out "$HOME/checkpoints/onpolicy" \
  --n 4 --temp 0.8 --adapter A_qa3=$HOME/checkpoints/A_qa3/adapter
echo OP_SAMPLE_DONE
