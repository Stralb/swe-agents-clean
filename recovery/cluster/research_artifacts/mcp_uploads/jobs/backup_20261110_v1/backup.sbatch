#!/bin/bash
#SBATCH --job-name=arno-verified-hf-backup
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=12:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/backup_20261110_v1/backup.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/backup_20261110_v1/backup.err
/home-mscluster/astrauss/.venvs/huggingface/bin/python /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/backup_20261110_v1/backup.py
