#!/bin/bash
#SBATCH --job-name=arno_schema_pack
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_full_schema_export_20261031_v1/compress.py
