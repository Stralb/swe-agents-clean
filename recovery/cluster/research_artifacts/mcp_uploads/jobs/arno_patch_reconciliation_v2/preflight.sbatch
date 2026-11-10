#!/bin/bash
#SBATCH --job-name=arno_exp_patches_preflight
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/preflight.py
