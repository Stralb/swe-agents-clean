#!/bin/bash
#SBATCH --job-name=OWP14P_CodeQL
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71201
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=14:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v3/scan14.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v3/scan14.py"
