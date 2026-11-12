#!/bin/bash
#SBATCH --job-name=arno_rpl7_after_stampede
#SBATCH --partition=stampede
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=18:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/log_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/log_%j.err
#SBATCH --array=0-3
set -euo pipefail
umask 077
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
CASES=(03581 08152 22223 32759)
CASE_ID="${CASES[$SLURM_ARRAY_TASK_ID]}"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/scan_case.py" --case "$CASE_ID"
