#!/usr/bin/env bash
# Serving export of the deployed adapter A_qa3_dpo3 (brief item 7): merge into the bf16 base in memory (top-1 agreement gate),
# AWQ 4-bit export, then the same evaluation drafts and latency benchmark on vLLM for base + adapter (bf16) and the AWQ model.
#SBATCH --job-name=quant
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
M="$HOME/models"
Q="$HOME/checkpoints/quant"
mkdir -p "$M" "$Q"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

echo "== 1-2. merge (in memory, gated) and AWQ"
if [ ! -f "$M/A_qa3_dpo3_awq/quant_info.json" ]; then
  "$HOME/venv-teacher/bin/python" vm/quant_awq.py --adapter "$HOME/checkpoints/A_qa3_dpo3/run/adapter" --out "$M/A_qa3_dpo3_awq"
fi
cat "$M/A_qa3_dpo3_awq/quant_info.json"

echo "== 3. evaluate and time"
"$HOME/venv-teacher/bin/python" vm/quant_eval.py --model BASE --adapter "$HOME/checkpoints/A_qa3_dpo3/run/adapter" --name bf16_lora --out "$Q"
"$HOME/venv-teacher/bin/python" vm/quant_eval.py --model "$M/A_qa3_dpo3_awq" --name awq --out "$Q"
du -sh "$M/A_qa3_dpo3_awq"
echo "QUANT_DONE"
