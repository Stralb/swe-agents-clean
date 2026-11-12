#!/bin/bash
#SBATCH --job-name=seven_codeql_recheck
#SBATCH --partition=bigbatch
#SBATCH --array=0,6
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
ids=(03429 03581 08152 12344 22223 31207 32759)
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_new_scans_20261020_v1/scan.py" "${ids[$SLURM_ARRAY_TASK_ID]}"
