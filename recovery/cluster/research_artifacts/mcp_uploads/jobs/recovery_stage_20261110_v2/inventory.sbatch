#!/bin/bash
#SBATCH --job-name=arno-recovery-inventory
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recovery_stage_20261110_v2/inventory.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recovery_stage_20261110_v2/inventory.err
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recovery_stage_20261110_v2/inventory.py
