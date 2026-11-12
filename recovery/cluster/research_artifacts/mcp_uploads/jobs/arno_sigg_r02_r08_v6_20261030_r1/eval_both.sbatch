#!/bin/bash
#SBATCH --job-name=arno_SIGG02_08
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --array=0-1%2
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
RUNS=(R02 R08)
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_sigg_r02_r08_v6_20261030_r1/eval_run.py "${RUNS[$SLURM_ARRAY_TASK_ID]}"
