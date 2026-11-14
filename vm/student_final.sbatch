#!/usr/bin/env bash
# Final student steps: (1) red-team of A_qa_dpo, (2) merge the adapter with a numerical check, (3) smoke test of the
# merged model behind an OpenAI-compatible server. Frees the teacher model first (its jobs are finished; re-downloadable).
#SBATCH --job-name=student-final
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
cd "$HOME/sme"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
rm -rf "$HOME/models/Qwen3-32B-AWQ"; echo "freed teacher model"; quota -s | tail -1
ADAPTER="$HOME/checkpoints/A_qa_dpo/run/adapter"

echo "== 1. red team"
source "$HOME/venv-teacher/bin/activate"
export VLLM_ENGINE_READY_TIMEOUT_S=3600
python vm/red_team.py --prompts evaluate/red_team_prompts.json --corpus rag/corpus_test.jsonl \
  --adapter "$ADAPTER" --out "$HOME/sme/eval/red_team.jsonl"
deactivate

echo "== 2. merge"
source "$HOME/venv/bin/activate"
python vm/merge_adapter.py --adapter "$ADAPTER" --test trainset/out/test_v2.jsonl --out "$HOME/models/A_qa_dpo_merged"
deactivate

echo "== 3. serve smoke test"
source "$HOME/venv-teacher/bin/activate"
vllm serve "$HOME/models/A_qa_dpo_merged" --port 8011 --served-model-name sme-drhp-7b --max-model-len 6144 \
  --gpu-memory-utilization 0.85 > logs/serve_merged.log 2>&1 &
SERVE=$!
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8011/v1/models >/dev/null && break; sleep 10; done
curl -s http://127.0.0.1:8011/v1/models | head -c 300; echo
curl -s http://127.0.0.1:8011/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"sme-drhp-7b","temperature":0,"max_tokens":120,"messages":[{"role":"system","content":"You are DRHP Assistant. Answer only from the EVIDENCE and cite [n]."},{"role":"user","content":"EVIDENCE:\n[1] PASSAGE Business, Overview: The Company was incorporated on 12 March 2015 at Pune and manufactures packaging films.\n\nQUESTION: When was the company incorporated?"}]}' | head -c 800; echo
kill $SERVE 2>/dev/null || true
pkill -f "vllm serve" 2>/dev/null || true
echo "STUDENT_FINAL_DONE"
