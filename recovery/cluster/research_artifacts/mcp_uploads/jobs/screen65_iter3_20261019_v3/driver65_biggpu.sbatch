#!/bin/bash
#SBATCH --job-name=screen65_it3_full
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71488
#SBATCH --cpus-per-task=9
#SBATCH --mem=64G
#SBATCH --time=2-00:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v3/driver65.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v3/driver65.py"
