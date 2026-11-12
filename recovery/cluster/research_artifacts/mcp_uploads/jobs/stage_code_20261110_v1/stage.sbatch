#!/bin/bash
#SBATCH --job-name=arno-stage-source
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/stage_code_20261110_v1/stage.py
