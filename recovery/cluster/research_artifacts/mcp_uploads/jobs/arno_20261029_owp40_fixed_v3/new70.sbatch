#!/bin/bash
#SBATCH --job-name=arno_new70_src_v3
#SBATCH --partition=batch
#SBATCH --dependency=afterok:77891
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/new70_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/new70_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_new70_orig_embed/embed.py --apply
