#!/bin/bash
#SBATCH --job-name=arno_schema_20261031
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_full_schema_export_20261031_v1/schema-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_full_schema_export_20261031_v1/schema-%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_full_schema_export_20261031_v1/export.py
