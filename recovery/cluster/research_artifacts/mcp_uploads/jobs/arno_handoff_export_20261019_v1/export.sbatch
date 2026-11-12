#!/bin/bash
#SBATCH --job-name=ARNO_export
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=03:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_export_20261019_v1/export.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/arno_handoff_export_20261019_v1/export.py"
