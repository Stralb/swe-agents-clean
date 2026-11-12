#!/bin/bash
#SBATCH --job-name=arno_ro_audit
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_master_readonly_audit_20261028/audit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_master_readonly_audit_20261028/audit_%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_master_readonly_audit_20261028/audit.py
