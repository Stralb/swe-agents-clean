#!/bin/bash
#SBATCH --job-name=seven_case_repair
#SBATCH --partition=bigbatch
#SBATCH --array=0-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:30:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
ids=(03429 08152 12344 31207)
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_targeted_fixes_20261020_v1/fix_scan.py" "${ids[$SLURM_ARRAY_TASK_ID]}"
