#!/bin/bash
#SBATCH --job-name=arno_v6_reconcile
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_gap_forensics_20261101"
python3 -B build_v6_release.py
