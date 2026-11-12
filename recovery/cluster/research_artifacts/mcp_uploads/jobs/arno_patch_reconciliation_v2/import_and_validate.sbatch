#!/bin/bash
#SBATCH --job-name=arno_patch_reconcile_v2
#SBATCH --partition=stampede
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --dependency=afterok:79596
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/import_fixed.py
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_reconciliation_v2/validate.py
