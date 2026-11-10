#!/bin/bash
#SBATCH --job-name=prev_p2_v2
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00
#SBATCH --array=0-2%1
#SBATCH --output=phase2_v2_%A_%a.out
#SBATCH --error=phase2_v2_%A_%a.err

set -euo pipefail
export PHASE2_ROOT=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2
cd "$PHASE2_ROOT"
CASES=(3504 10819 629)
CID="${CASES[$SLURM_ARRAY_TASK_ID]}"
python3 -u phase2_eval_v2.py --case "$CID"
