#!/bin/bash
#SBATCH --job-name=arno_v7_owp_inputs
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_v7_owp_input_reconciliation_20261101"
python3 -B import_verified_inputs.py
