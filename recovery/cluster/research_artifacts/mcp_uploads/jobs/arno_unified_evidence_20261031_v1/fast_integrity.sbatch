#!/bin/bash
#SBATCH --job-name=arno_unified_fast_gate
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/fast_integrity.py
