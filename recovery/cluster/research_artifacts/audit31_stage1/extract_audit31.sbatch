#!/bin/bash
#SBATCH --job-name=audit31_ext
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/audit31_stage1/extract.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/audit31_stage1/extract.err

set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/audit31_stage1/extract_audit31.py
