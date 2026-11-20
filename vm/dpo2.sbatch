#!/usr/bin/env bash
# DPO round 2 for A_qa3: the abstention pairs (chosen [●], rejected states a missing value) now balanced by keep pairs
# (chosen states the fact that IS in FACTS, rejected blanks it), plus the loop pairs of round 1. Then best-of-3 drafts for A_qa3 (SFT only) and A_qa3_dpo2.
#SBATCH --job-name=qa3-dpo2
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
D="$HOME/checkpoints/A_qa3_dpo2"
mkdir -p "$D"
cat "$HOME/checkpoints/A_qa3_dpo/loop_pairs.jsonl" trainset/out/abstain_pairs.jsonl trainset/out/keep_pairs.jsonl | shuf --random-source=<(yes 7) > "$D/pairs.jsonl"
wc -l "$D/pairs.jsonl"
"$HOME/venv/bin/python" vm/dpo_train.py --src-adapter "$SRC" --pairs "$D/pairs.jsonl" --out "$D/run"
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$D/run/adapter" --test trainset/out/test_app.jsonl --out "$D/app" --name A_qa3_dpo2
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$SRC" --test trainset/out/test_app.jsonl --out "$HOME/checkpoints/A_qa3/app" --name A_qa3
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$D/run/adapter" --test trainset/out/test_v2.jsonl --out "$D" --name A_qa3_dpo2
"$HOME/venv-teacher/bin/python" vm/predict_bon.py --test trainset/out/test_app.jsonl --out "$HOME/checkpoints/bon2" \
  --adapter A_qa3=$SRC --adapter A_qa3_dpo2=$D/run/adapter
echo "DPO2_DONE"
