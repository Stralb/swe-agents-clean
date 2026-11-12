#!/bin/bash
#SBATCH --job-name=hist_ctrl_v1
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --array=0-2%2
#SBATCH --output=hist_ctrl_v1_%A_%a.out
#SBATCH --error=hist_ctrl_v1_%A_%a.err

set -euo pipefail
export PHASE2_ROOT=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2
cd "$PHASE2_ROOT"
CASES=(3504 10819 629)
python3 -u phase2_historical_control_v1.py "${CASES[$SLURM_ARRAY_TASK_ID]}"
