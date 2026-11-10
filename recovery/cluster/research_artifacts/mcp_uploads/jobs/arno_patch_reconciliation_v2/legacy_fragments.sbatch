#!/bin/bash
#SBATCH --job-name=arno_prior_fragments_v2
#SBATCH --partition=stampede
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --dependency=afterok:79597
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/legacy_fragments.py
