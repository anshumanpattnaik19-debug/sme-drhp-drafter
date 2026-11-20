#!/usr/bin/env bash
# Run 14: DPO on top of A_qa3 with on-policy pairs (data/onpolicy_pairs.py), then the evaluation drafts.
#SBATCH --job-name=qa3-dpo3
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
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
SRC="$HOME/checkpoints/A_qa3/adapter"
D="$HOME/checkpoints/A_qa3_dpo3"
mkdir -p "$D"
wc -l trainset/out/onpolicy_pairs.jsonl
"$HOME/venv/bin/python" vm/dpo_train.py --src-adapter "$SRC" --pairs trainset/out/onpolicy_pairs.jsonl --out "$D/run" --lr "${DPO_LR:-5e-6}" --epochs "${DPO_EPOCHS:-2}"
"$HOME/venv-teacher/bin/python" vm/predict_bon.py --test trainset/out/test_app.jsonl --out "$D/bon" --adapter A_qa3_dpo3=$D/run/adapter
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$D/run/adapter" --test trainset/out/test_v2.jsonl --out "$D" --name A_qa3_dpo3
echo "DPO3_DONE"
