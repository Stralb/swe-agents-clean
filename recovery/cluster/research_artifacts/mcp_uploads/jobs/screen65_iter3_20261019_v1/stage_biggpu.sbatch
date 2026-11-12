#!/bin/bash
#SBATCH --job-name=screen65_it3_stage
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v1/stage.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_20261019_v1/stage.py"
