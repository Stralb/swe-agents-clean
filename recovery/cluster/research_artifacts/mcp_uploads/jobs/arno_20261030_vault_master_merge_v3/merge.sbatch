#!/bin/bash
#SBATCH --job-name=arno_merge_vault_into_master
#SBATCH --partition=batch
#SBATCH --dependency=afterok:78116:78131
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_vault_master_merge_v3/%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_vault_master_merge_v3/%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_vault_master_merge_v3/merge.py
