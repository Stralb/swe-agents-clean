#!/bin/bash
#SBATCH --job-name=seven_codeql_08152
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_new_scans_20261020_v1/scan.py" 08152
