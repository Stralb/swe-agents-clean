#!/bin/bash
#SBATCH --job-name=arno_owp40_verify
#SBATCH --dependency=afterok:77360
#SBATCH --time=00:25:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp40_postcheck_20261028/postcheck_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp40_postcheck_20261028/postcheck_%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp40_postcheck_20261028/postcheck.py
