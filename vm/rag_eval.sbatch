#!/usr/bin/env bash
# Agentic RAG (rag_base and rag_A_qa_dpo), the B1 two-shot baseline, and Q&A retrieval recall, in one job.
# Submit from ~/sme:   sbatch vm/rag_eval.sbatch
#SBATCH --job-name=rag-eval
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
source "$HOME/venv-teacher/bin/activate"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python vm/rag_eval.py --test trainset/out/test_v2.jsonl --train trainset/out/train_v2.jsonl \
  --corpus rag/corpus_test.jsonl --adapter "$HOME/checkpoints/A_qa_dpo/run/adapter" --out "$HOME/checkpoints/rag"
