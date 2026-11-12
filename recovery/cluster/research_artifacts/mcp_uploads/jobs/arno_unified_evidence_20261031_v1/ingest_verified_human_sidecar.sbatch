#!/bin/bash
#SBATCH --job-name=arno_full_human_sidecar
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/ingest_verified_human_sidecar.py
