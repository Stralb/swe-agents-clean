#!/bin/bash
#SBATCH --job-name=arno_owp40_v2
#SBATCH --dependency=afterok:77728
#SBATCH --time=01:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/owp_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/owp_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/normalize.py --apply
