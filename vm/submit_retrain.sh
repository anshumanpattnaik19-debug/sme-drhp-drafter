#!/usr/bin/env bash
# Submit the A_qa3 retraining: SFT first, then DPO and the evaluation predictions once the SFT job has succeeded.
set -Eeuo pipefail
cd "$HOME/sme"
mkdir -p logs
J1=$(sbatch --parsable vm/retrain_sft.sbatch)
echo "SFT job $J1"
J2=$(sbatch --parsable --dependency=afterok:"$J1" vm/retrain_dpo.sbatch)
echo "DPO job $J2 (after $J1)"
squeue -u "$USER"
