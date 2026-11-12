#!/bin/bash
#SBATCH --job-name=OWP14OP_report
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:71204
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v5/report_op.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v5/report_op.py"
