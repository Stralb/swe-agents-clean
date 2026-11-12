#!/bin/bash
#SBATCH --job-name=arno_rpl7_scan_31207
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:78462
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=18:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/patched_31207_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/patched_31207_%j.err
set -euo pipefail
umask 077
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/scan_case.py" --case 31207
