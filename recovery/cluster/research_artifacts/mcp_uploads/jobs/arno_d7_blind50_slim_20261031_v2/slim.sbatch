#!/bin/bash
#SBATCH --job-name=arno_d7_compact
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_d7_blind50_slim_20261031_v2/slim.py
