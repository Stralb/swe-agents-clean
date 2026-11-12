#!/bin/bash
#SBATCH --job-name=arno_d7_blind50_fix
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_sample_50_20261031_v3/export_fixed.py
