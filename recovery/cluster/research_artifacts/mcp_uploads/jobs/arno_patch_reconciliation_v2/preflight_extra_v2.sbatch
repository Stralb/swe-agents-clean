#!/bin/bash
#SBATCH --job-name=arno_deep_input_hash_gate
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/preflight_extra_v2.py
