#!/bin/bash
#SBATCH --job-name=arno_owp40_afterbackup
#SBATCH --dependency=afterok:77347
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_owp40_normalize/dependent_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_owp40_normalize/dependent_%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_owp40_normalize/normalize.py --apply
