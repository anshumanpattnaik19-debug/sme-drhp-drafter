#!/usr/bin/env bash
# Run A_qa3 on the course VM: run A_qa's settings on train_v3.jsonl (train_v2 plus 306 abstention variants, precedent removed
# from 60% of drafting rows; data/abstain.py), about 70 to 100 minutes on an L40S.
# Submit from ~/sme:   cd ~/sme && sbatch vm/retrain_sft.sbatch      then:   sbatch --dependency=afterok:<jobid> vm/retrain_dpo.sbatch
#SBATCH --job-name=qa3-train
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv/bin/activate"
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python vm/train_qa.py --train trainset/out/train_v3.jsonl --out "$HOME/checkpoints/A_qa3"
echo "SFT_DONE"
