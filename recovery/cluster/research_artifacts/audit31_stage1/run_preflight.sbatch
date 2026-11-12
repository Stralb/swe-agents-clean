#!/bin/bash
#SBATCH --job-name=audit31_pre
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/audit31_stage1/preflight.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/audit31_stage1/preflight.err

set -euo pipefail
cd /home-mscluster/astrauss/research_artifacts/audit31_stage1
python3 audit31_db_preflight.py
