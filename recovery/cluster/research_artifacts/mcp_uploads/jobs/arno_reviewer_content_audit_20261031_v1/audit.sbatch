#!/bin/bash
#SBATCH --job-name=arno_content_triage
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_reviewer_content_audit_20261031_v1/audit.py
