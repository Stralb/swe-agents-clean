#!/bin/bash
#SBATCH --job-name=arno_new70_embed
#SBATCH --dependency=afterok:77365
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_new70_orig_embed/apply_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_new70_orig_embed/apply_%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_new70_orig_embed/embed.py --apply
