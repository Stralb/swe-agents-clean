#!/bin/bash
#SBATCH --job-name=ARNO_addendum2
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:45:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_supplement_20261019_v2/supplement.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_supplement_20261019_v2/supplement.py"
