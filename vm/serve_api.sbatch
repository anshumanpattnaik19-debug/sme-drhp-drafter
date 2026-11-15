#!/usr/bin/env bash
# Serve the drafting model (base + A_qa_dpo LoRA adapter) with vLLM on the VM's network address, behind an API key, so
# the app can run on another machine (for example the Docker container on the laptop). The key is read from
# ~/sme/serve.key (mode 600) and is never written to the logs. Stops after the time window.
#SBATCH --job-name=serve-api
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
cd "$HOME/sme"
BASE=$(cat /storage/tracka/models/base_model_path.txt)
ADAPTER="$HOME/checkpoints/A_qa_dpo/run/adapter"
KEY=$(cat "$HOME/sme/serve.key")
vllm serve "$BASE" --host 0.0.0.0 --port 8011 --api-key "$KEY" --max-model-len 6144 --gpu-memory-utilization 0.85 \
  --enable-lora --max-lora-rank 16 --lora-modules "sme-drhp-7b=$ADAPTER" > logs/serve_api.log 2>&1 &
SERVE=$!
trap 'kill $SERVE 2>/dev/null || true; pkill -f "vllm serve" 2>/dev/null || true' EXIT
for i in $(seq 1 90); do
  if curl -sf -H "Authorization: Bearer $KEY" http://127.0.0.1:8011/v1/models >/dev/null; then echo "SERVING"; break; fi
  sleep 10
done
sleep 4800
echo "SERVE_WINDOW_END"
