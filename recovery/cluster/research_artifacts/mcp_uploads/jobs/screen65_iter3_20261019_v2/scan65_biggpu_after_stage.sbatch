#!/bin/bash
#SBATCH --job-name=screen65_it3_CodeQL
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71488
#SBATCH --array=0-64%3
#SBATCH --cpus-per-task=3
#SBATCH --mem=20G
#SBATCH --time=03:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:/usr/bin:/bin"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v2/scan65.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v2/scan65.py"
