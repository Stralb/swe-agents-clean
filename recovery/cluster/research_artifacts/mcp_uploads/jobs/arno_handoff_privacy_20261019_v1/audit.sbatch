#!/bin/bash
#SBATCH --job-name=ARNO_privacy
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_privacy_20261019_v1/audit.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_privacy_20261019_v1/audit.py"
