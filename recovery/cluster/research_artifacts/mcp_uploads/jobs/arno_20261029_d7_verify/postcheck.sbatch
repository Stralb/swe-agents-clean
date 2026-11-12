#!/bin/bash
#SBATCH --job-name=arno_d7_postcheck
#SBATCH --dependency=afterok:77726
#SBATCH --time=00:25:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_d7_verify/postcheck_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_d7_verify/postcheck_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_d7_verify/verify.py
