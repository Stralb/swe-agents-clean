#!/bin/bash
#SBATCH --job-name=OWP_Archive
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp_full_handoff_20261019_v1/bundle.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_full_handoff_20261019_v1/bundle.py"
