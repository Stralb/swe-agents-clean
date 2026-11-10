#!/bin/bash
#SBATCH --job-name=arno_owp40_postcheck_v3
#SBATCH --partition=batch
#SBATCH --dependency=afterok:77890
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/postcheck_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/postcheck_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp40_postcheck_20261028/postcheck.py
