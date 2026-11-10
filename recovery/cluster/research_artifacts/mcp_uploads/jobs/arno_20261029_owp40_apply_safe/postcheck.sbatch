#!/bin/bash
#SBATCH --job-name=arno_owp40_check
#SBATCH --dependency=afterok:77733
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/check_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/check_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp40_postcheck_20261028/postcheck.py
