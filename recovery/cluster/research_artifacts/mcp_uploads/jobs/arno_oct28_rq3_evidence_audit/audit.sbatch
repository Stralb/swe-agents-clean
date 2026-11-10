#!/bin/bash
#SBATCH --job-name=arno_rq3_audit
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_rq3_evidence_audit/audit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_rq3_evidence_audit/audit_%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_oct28_rq3_evidence_audit/audit.py
