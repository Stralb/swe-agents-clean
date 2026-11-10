#!/bin/bash
#SBATCH --job-name=OWP14W_CodeQL
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71208:71204
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=14:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_w_20261018_v2/scan14.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_w_20261018_v2/scan14.py"
