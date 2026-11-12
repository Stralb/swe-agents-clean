#!/bin/bash
#SBATCH --job-name=arno_manuscript_claim_audit
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_paper_claim_reconcile_20261031_v1/build.py
