#!/bin/bash
#SBATCH --job-name=arno_ac6_v6c
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --array=0-11%2
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/slurm_v6c_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/slurm_v6c_%A_%a.err
set -euo pipefail
umask 077
export PATH="$HOME/tools/node24/bin:$HOME/tools/codeql:$PATH"
node --version
python3 -m py_compile "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/scan_ac_v6c.py"
test -f "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/scan_ac_v6c.py" --index "$SLURM_ARRAY_TASK_ID"
