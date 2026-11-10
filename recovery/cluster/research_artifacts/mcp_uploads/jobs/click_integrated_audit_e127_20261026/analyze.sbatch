#!/bin/bash
#SBATCH --job-name=e127fullaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:14:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_integrated_audit_e127_20261026
python3 -m py_compile "$ROOT/analyze.py"
python3 "$ROOT/analyze.py"
echo E127_FULL_AUDIT_JOB_FINISHED
