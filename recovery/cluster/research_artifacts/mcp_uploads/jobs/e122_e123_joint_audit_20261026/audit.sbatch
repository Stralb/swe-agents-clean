#!/bin/bash
#SBATCH --job-name=e122e123audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e122_e123_joint_audit_20261026
python3 -m py_compile "$ROOT/analyze.py"
python3 "$ROOT/analyze.py"
echo E122_E123_REPRODUCIBILITY_AUDIT_SUCCESS
