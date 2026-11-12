#!/bin/bash
#SBATCH --job-name=arno_erd_transfer
#SBATCH --partition=stampede
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_erd_schema_transfer_20261031_v1/mini.py
