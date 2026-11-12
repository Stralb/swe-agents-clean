#!/bin/bash
#SBATCH --job-name=arno_new_relations_ro
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_new_relations_phasec_20261101_v1"
python3 -B readonly_extract.py
