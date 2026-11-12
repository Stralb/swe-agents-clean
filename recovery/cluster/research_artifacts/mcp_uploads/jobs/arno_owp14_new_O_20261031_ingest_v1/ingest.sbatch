#!/bin/bash
#SBATCH --job-name=owp_new_o_ingest
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_ingest_v1/ingest-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_ingest_v1/ingest-%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_ingest_v1/ingest.py
