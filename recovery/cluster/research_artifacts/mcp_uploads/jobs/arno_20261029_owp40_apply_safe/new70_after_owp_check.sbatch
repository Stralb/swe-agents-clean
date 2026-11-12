#!/bin/bash
#SBATCH --job-name=arno_new70_sources
#SBATCH --dependency=afterok:77734
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/new70_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_apply_safe/new70_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_new70_orig_embed/embed.py --apply
