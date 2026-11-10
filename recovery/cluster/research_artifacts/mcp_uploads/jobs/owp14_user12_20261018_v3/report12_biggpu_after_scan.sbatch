#!/bin/bash
#SBATCH --job-name=OWP12O_report
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71159
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user12_20261018_v3/report12.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user12_20261018_v3/report12.py"
