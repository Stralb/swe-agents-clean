#!/bin/bash
#SBATCH --job-name=OWP14P_v2b
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v2b/preflight.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user14_p_20261018_v2b/preflight.py"
