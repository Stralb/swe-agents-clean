#!/bin/bash
#SBATCH --job-name=arno_deep_fast_qa
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/validate_bounded.py
