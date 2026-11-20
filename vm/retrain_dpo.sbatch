#!/usr/bin/env bash
# DPO for run A_qa3 in one job, then the predictions that decide whether it ships:
#   1. loop pairs      A_qa3 drafts 400 training prompts; looped or capped drafts become 'rejected'   (vLLM: ~/venv-teacher)
#   2. merge           the loop pairs plus the 306 abstention pairs (chosen = [●], rejected = states a value the prompt lacks)
#   3. train           DPO on top of A_qa3, reference = the starting adapter                            (QLoRA: ~/venv)
#   4. predict         A_qa3_dpo on test_v2 (all skills) and test_app (drafting, the prompt the app sends), with the base;
#                      the shipped A_qa_dpo on test_app, same decoding, for the comparison
# Submit after the SFT job:   sbatch --dependency=afterok:<sft jobid> vm/retrain_dpo.sbatch
#SBATCH --job-name=qa3-dpo
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=05:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
SRC="$HOME/checkpoints/A_qa3/adapter"
DPO="$HOME/checkpoints/A_qa3_dpo"
OLD="$HOME/checkpoints/A_qa_dpo/run/adapter"
mkdir -p "$DPO"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

echo "== 1. loop pairs"
"$HOME/venv-teacher/bin/python" vm/dpo_pairs.py --adapter "$SRC" --train trainset/out/train_v3.jsonl --out "$DPO/loop_pairs.jsonl" \
  || echo "loop pairs step failed or found too few: continuing with the abstention pairs alone"

echo "== 2. merge"
"$HOME/venv/bin/python" - <<'PY'
import json, os, random
d = os.path.expanduser("~/checkpoints/A_qa3_dpo")
rows = []
for path in (f"{d}/loop_pairs.jsonl", "trainset/out/abstain_pairs.jsonl"):
    if os.path.exists(path):
        rows += [json.loads(l) for l in open(path) if l.strip()]
        print(path, len(rows), flush=True)
random.Random(7).shuffle(rows)
open(f"{d}/pairs.jsonl", "w").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
print("merged pairs", len(rows), flush=True)
PY

echo "== 3. train"
"$HOME/venv/bin/python" vm/dpo_train.py --src-adapter "$SRC" --pairs "$DPO/pairs.jsonl" --out "$DPO/run"

echo "== 4. predict"
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$DPO/run/adapter" --test trainset/out/test_v2.jsonl --out "$DPO" --name A_qa3_dpo
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$DPO/run/adapter" --test trainset/out/test_app.jsonl --out "$DPO/app" --name A_qa3_dpo --with-base
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$OLD" --test trainset/out/test_app.jsonl --out "$HOME/checkpoints/A_qa_dpo/app" --name A_qa_dpo
echo "RETRAIN_DONE"
