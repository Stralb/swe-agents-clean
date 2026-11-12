#!/bin/bash
#SBATCH --job-name=arno_full_clone_v2
#SBATCH --partition=stampede
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/clone.py
