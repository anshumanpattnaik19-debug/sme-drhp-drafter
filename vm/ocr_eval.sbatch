#!/usr/bin/env bash
# OCR error-rate test on the VM: serve the vision model with vLLM, transcribe the test pages (vm/ocr_eval_vllm.py),
# then stop the server. Scoring is done on the laptop (vm/ocr_eval_score.py) against the digital text.
#SBATCH --job-name=ocr-eval
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
M="$HOME/models/Qwen2.5-VL-7B-Instruct"
vllm serve "$M" --port 8012 --served-model-name qwen-vl --max-model-len 6144 \
  --gpu-memory-utilization 0.85 --limit-mm-per-prompt '{"image": 1}' > logs/ocr_serve.log 2>&1 &
SERVE=$!
trap 'kill $SERVE 2>/dev/null || true; pkill -f "vllm serve" 2>/dev/null || true' EXIT
ok=0
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8012/v1/models >/dev/null; then ok=1; break; fi
  sleep 10
done
echo "vLLM ready: $ok"
[ "$ok" = "1" ] || { tail -50 logs/ocr_serve.log; exit 1; }
python -W ignore vm/ocr_eval_vllm.py ocr_eval http://127.0.0.1:8012/v1 qwen-vl ocr_eval/transcripts_qwen_vl.json
echo "OCR_EVAL_END"
