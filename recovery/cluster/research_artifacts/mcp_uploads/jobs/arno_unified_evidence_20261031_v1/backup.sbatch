#!/bin/bash
#SBATCH --job-name=arno_full_safe_clone
#SBATCH --partition=stampede
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/backup.py
