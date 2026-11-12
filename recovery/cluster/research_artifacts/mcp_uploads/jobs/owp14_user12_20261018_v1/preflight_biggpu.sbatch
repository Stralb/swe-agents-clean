#!/bin/bash
#SBATCH --job-name=OWP12O_preflight
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user12_20261018_v1/preflight.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_user12_20261018_v1/preflight.py"
