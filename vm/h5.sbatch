#!/usr/bin/env bash
# H5 on the course VM: serve the merged A_qa_dpo model with vLLM, then run the app end to end on the five
# issuer bundles (vm/h5_run.py), then stop the server. Drafting goes through the OpenAI-compatible vLLM server,
# not the offline mock.
#SBATCH --job-name=h5-bundles
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
cd "$HOME/sme"
M="$HOME/models/A_qa_dpo_merged"
vllm serve "$M" --port 8011 --served-model-name sme-drhp-7b --max-model-len 6144 \
  --gpu-memory-utilization 0.85 > logs/h5_serve.log 2>&1 &
SERVE=$!
trap 'kill $SERVE 2>/dev/null || true; pkill -f "vllm serve" 2>/dev/null || true' EXIT
ok=0
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8011/v1/models >/dev/null; then ok=1; break; fi
  sleep 10
done
echo "vLLM ready: $ok"
[ "$ok" = "1" ] || { tail -50 logs/h5_serve.log; exit 1; }
python -W ignore vm/h5_run.py
echo "H5_JOB_END"
