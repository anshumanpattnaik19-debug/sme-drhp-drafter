#!/usr/bin/env bash
# Teacher baseline B3 (2-shot) and the LLM-as-judge pass (Qwen3-32B-AWQ). Submit from ~/sme: sbatch vm/teacher_eval.sbatch
#SBATCH --job-name=teacher-eval
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python vm/teacher_eval.py --test trainset/out/test_v2.jsonl --train trainset/out/train_v2.jsonl --eval "$HOME/sme/eval/out" \
  --judge A_qa_dpo=eval/inputs/predictions_A_qa_dpo.jsonl base=eval/inputs/predictions_base.jsonl \
          B1_2shot=eval/inputs/predictions_B1_2shot.jsonl rag_F2=eval/inputs/predictions_rag_A_qa_dpo.jsonl
