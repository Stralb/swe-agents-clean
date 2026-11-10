#!/bin/bash
#SBATCH --job-name=two_provider_codeql
#SBATCH --partition=bigbatch
#SBATCH --array=0-1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:30:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
ids=(08152 31207)
id="${ids[$SLURM_ARRAY_TASK_ID]}"
dir="$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v1"
python3 "$dir/init.py" "$id"
python3 "$dir/modify.py" "$id"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v2/scan.py" "$id"
