#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/sme"; mkdir -p logs
sbatch --parsable --dependency=afterany:"$1" vm/dpo2.sbatch
