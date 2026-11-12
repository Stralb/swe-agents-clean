#!/bin/bash
#SBATCH --job-name=arno_review50_merge_v2
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_d7_human_review_ingest_20261031_v1/merge_v2.py
