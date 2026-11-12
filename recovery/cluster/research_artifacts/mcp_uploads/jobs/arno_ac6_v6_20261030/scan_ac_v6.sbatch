#!/bin/bash
#SBATCH --job-name=arno_ac6_codeql_v6
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --array=0-11%3
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/slurm_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/slurm_%A_%a.err
set -euo pipefail
umask 077
test -f "$HOME/research_artifacts/mcp_uploads/arno_ac_six_20261030/ARNO_A_C_ALL12_EVIDENCE_INPUT.zip" || { echo "Evidence ZIP must be uploaded first"; exit 2; }
python3 -m py_compile "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/scan_ac_v6.py"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/scan_ac_v6.py" --index "$SLURM_ARRAY_TASK_ID"
