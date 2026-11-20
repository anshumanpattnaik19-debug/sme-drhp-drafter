#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/sme"; mkdir -p logs
sbatch --parsable vm/bon.sbatch
