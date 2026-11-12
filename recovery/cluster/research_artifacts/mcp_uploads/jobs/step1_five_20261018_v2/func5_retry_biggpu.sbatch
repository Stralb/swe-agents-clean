#!/bin/bash
#SBATCH --job-name=O5func_retry
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=08:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export SLURM_ARRAY_JOB_ID="$SLURM_JOB_ID"
for i in $(seq 0 9); do
  export SLURM_ARRAY_TASK_ID="$i"
  echo "FUNCTIONAL_RETRY_TASK_START $i"
  python3 "$HOME/research_artifacts/mcp_uploads/jobs/step1_five_20261018_v2/func5_fixed.py" || echo "FUNCTIONAL_RETRY_TASK_FAILED $i"
done
