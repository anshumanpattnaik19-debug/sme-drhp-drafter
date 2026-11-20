#!/usr/bin/env bash
# RAG with documented choices (brief item 5): retrieval benchmark (BM25, bge-m3, hybrid, bge-reranker-v2-m3), then base + RAG and
# fine-tuned + RAG drafts with the contexts of the retriever with the best recall@5 (vm/best_retriever.py). Retrieval models load from /tmp (outside the home quota).
#SBATCH --job-name=rag2
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
export VLLM_ENGINE_READY_TIMEOUT_S=3600
export HF_HOME=/tmp/hf_learner05
mkdir -p "$HF_HOME"
cd "$HOME/sme"
O="$HOME/checkpoints/rag2"
"$HOME/venv-teacher/bin/python" vm/retrieval_eval.py --test trainset/out/test_v2.jsonl --corpus rag/corpus_test.jsonl --out "$O"
BEST=$("$HOME/venv-teacher/bin/python" vm/best_retriever.py "$O/retrieval_eval.json")
echo "best retriever by recall@5: $BEST"
"$HOME/venv-teacher/bin/python" vm/rag_gen.py --contexts "$O/contexts_${RAG_CONTEXTS:-$BEST}.jsonl" \
  --adapter "$HOME/checkpoints/A_qa3_dpo3/run/adapter" --name A_qa3_dpo3 --out "$O"
echo "RAG2_DONE"
