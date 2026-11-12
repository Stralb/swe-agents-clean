#!/bin/bash
#SBATCH --job-name=arno-push-recovery
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:40:00
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/push_recovery_20261110_v1/push.py
