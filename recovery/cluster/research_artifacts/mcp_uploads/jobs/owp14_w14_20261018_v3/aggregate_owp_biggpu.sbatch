#!/bin/bash
#SBATCH --job-name=OWP14_allarm
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71209
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_w14_20261018_v3/aggregate_owp.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_w14_20261018_v3/aggregate_owp.py"
