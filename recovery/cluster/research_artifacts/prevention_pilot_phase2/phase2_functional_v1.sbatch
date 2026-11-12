#!/bin/bash
#SBATCH --job-name=prev_p2_func
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --array=0-2%2
#SBATCH --output=phase2_func_%A_%a.out
#SBATCH --error=phase2_func_%A_%a.err

set -euo pipefail
MINER="$HOME/new/malicious-issue-miner-rate-smart"
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"

# Reuse existing exports and venv; never create or install another Python environment.
set -a
source "$MINER/.env.cluster"
set +a
source "$MINER/.venv/bin/activate"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
export PHASE2_ROOT="$ROOT"
cd "$ROOT"

CASES=(3504 10819 629)
CASE="${CASES[$SLURM_ARRAY_TASK_ID]}"
python -u phase2_functional_v1.py --case "$CASE"
