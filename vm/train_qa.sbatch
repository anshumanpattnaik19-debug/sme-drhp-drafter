#!/usr/bin/env bash
# Run A_qa on the course VM: QLoRA on train_v2.jsonl (1,746 rows: drafting, extraction and Q&A), about 90 minutes on an L40S.
# Submit from ~/sme:   cd ~/sme && sbatch vm/train_qa.sbatch
#SBATCH --job-name=qa-train
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv/bin/activate"
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python vm/train_qa.py --train trainset/out/train_v2.jsonl --out "$HOME/checkpoints/A_qa-$SLURM_JOB_ID"
