#!/usr/bin/env bash
# Smoke test of the merged model behind an OpenAI-compatible server (vLLM 0.10, the same server the app talks to).
# Starts the server on the node, waits for it, sends one grounded question and one drafting request, then stops it.
#SBATCH --job-name=serve-smoke
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=00:40:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
cd "$HOME/sme"
M="$HOME/models/A_qa_dpo_merged"
vllm serve "$M" --port 8011 --served-model-name sme-drhp-7b --max-model-len 6144 --gpu-memory-utilization 0.85 \
  > logs/serve_merged.log 2>&1 &
SERVE=$!
ok=0
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8011/v1/models >/dev/null; then ok=1; break; fi
  sleep 10
done
echo "server ready: $ok"
curl -s http://127.0.0.1:8011/v1/models | head -c 300; echo
echo "--- Q&A"
curl -s http://127.0.0.1:8011/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"sme-drhp-7b","temperature":0,"max_tokens":120,"messages":[{"role":"system","content":"You are DRHP Assistant. Answer only from the EVIDENCE and cite [n]."},{"role":"user","content":"EVIDENCE:\n[1] PASSAGE Business, Overview: The Company was incorporated on 12 March 2015 at Pune and manufactures packaging films.\n\nQUESTION: When was the company incorporated?"}]}' | head -c 900; echo
echo "--- drafting"
curl -s http://127.0.0.1:8011/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"sme-drhp-7b","temperature":0,"max_tokens":200,"frequency_penalty":0.3,"messages":[{"role":"system","content":"You draft one sub-section of an SME Draft Red Herring Prospectus. Use only the FACTS given. Write [●] where a detail is missing."},{"role":"user","content":"COMPANY: Example Packaging Limited\nSECTION: BUSINESS\nSUB-HEADING: Overview\nFACTS: [{\"type\":\"date\",\"label\":\"incorporation\",\"value\":\"12 March 2015\"},{\"type\":\"entity\",\"label\":\"place\",\"value\":\"Pune\"}]\nDraft the sub-section now."}]}' | head -c 1200; echo
kill $SERVE 2>/dev/null || true
pkill -f "vllm serve" 2>/dev/null || true
echo "SERVE_SMOKE_DONE"
