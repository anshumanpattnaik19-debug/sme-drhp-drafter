#!/usr/bin/env bash
# Run 15: DPO on top of the deployed A_qa3_dpo3 with the Responsible AI pairs (data/rai_pairs.py: no spurious injection notices,
# PII refusals in 16 question forms, the same factual answer for every name, plus invest and drafting anchors), then the gates:
# best of 3 on test_app, test_v2 (all skills), and the RAI probes for base / A_qa3_dpo3 / the new adapter.
#SBATCH --job-name=rai-dpo
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
export VLLM_ENGINE_READY_TIMEOUT_S=3600
cd "$HOME/sme"
SRC="$HOME/checkpoints/A_qa3_dpo3/run/adapter"
D="$HOME/checkpoints/A_qa3_rai"
mkdir -p "$D"
wc -l trainset/out/rai_pairs.jsonl
if [ ! -f "$D/run/adapter/adapter_model.safetensors" ]; then
  "$HOME/venv/bin/python" vm/dpo_train.py --src-adapter "$SRC" --pairs trainset/out/rai_pairs.jsonl --out "$D/run" \
    --lr "${DPO_LR:-5e-6}" --epochs "${DPO_EPOCHS:-2}"
fi
"$HOME/venv-teacher/bin/python" vm/predict_bon.py --test trainset/out/test_app.jsonl --out "$D/bon" --adapter A_qa3_rai=$D/run/adapter
"$HOME/venv-teacher/bin/python" vm/predict_qa.py --adapter "$D/run/adapter" --test trainset/out/test_v2.jsonl --out "$D" --name A_qa3_rai
"$HOME/venv-teacher/bin/python" vm/rai_probes_vllm.py --out "$D/rai_probes_vm.jsonl" \
  --adapter sme-drhp-7b="$SRC" --adapter sme-drhp-7b-rai="$D/run/adapter"
echo "RAI_DPO_DONE"
