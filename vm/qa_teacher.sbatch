#!/usr/bin/env bash
# Stage 2c on the course VM: Qwen3-32B-AWQ (vLLM 0.10.0+cu126, ~/venv-teacher) writes the Q&A pairs for the 220 jobs
# in trainset/work/qa_jobs.jsonl -> ~/sme/out/qa_responses.jsonl. Resumable: resubmitting skips finished jobs.
#   cd ~/sme && sbatch vm/qa_teacher.sbatch
#SBATCH --job-name=qa-teacher
#SBATCH --partition=vm3_slurm_partition
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -Eeuo pipefail
source "$HOME/.tracka_environment"
source "$HOME/venv-teacher/bin/activate"
cd "$HOME/sme"
mkdir -p out logs
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python - <<'PY'
import json, os, sys
sys.path.insert(0, '.')
from teacher.serving import candidates, serve, stop
from teacher.driver import run

home = os.environ['HOME']
model = f'{home}/models/Qwen3-32B-AWQ'                   # downloaded by vm/setup_teacher.sh
args = candidates(46)['qwen3_32b_awq']['args']           # same serving arguments as the Colab teacher
jobs = [json.loads(l) for l in open('trainset/work/qa_jobs.jsonl', encoding='utf-8')]
print(f'{len(jobs)} jobs | model {model} | {args}', flush=True)
p = serve(model, args, log_dir=f'{home}/sme/logs')
try:
    print(run(jobs, f'{home}/sme/out/qa_responses.jsonl', 'http://localhost:8000/v1', model), flush=True)
finally:
    stop(p)
PY
