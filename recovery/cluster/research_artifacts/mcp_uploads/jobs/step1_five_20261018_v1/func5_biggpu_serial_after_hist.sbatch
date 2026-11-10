#!/bin/bash
#SBATCH --job-name=O5funcserial
#SBATCH --partition=biggpu
#SBATCH --dependency=afterany:70972
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=12:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export SLURM_ARRAY_JOB_ID="$SLURM_JOB_ID"
for i in $(seq 0 9); do
  export SLURM_ARRAY_TASK_ID="$i"
  echo "FUNCTIONAL_TASK_START $i"
  python3 "$HOME/research_artifacts/mcp_uploads/jobs/step1_five_20261018_v1/func5.py" || echo "FUNCTIONAL_TASK_FAILED $i"
done
