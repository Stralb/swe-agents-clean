#!/bin/bash
#SBATCH --job-name=arno_complete_evidence
#SBATCH --partition=stampede
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/evidence_recovered.py
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/validate_fixed.py
