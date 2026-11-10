#!/bin/bash
#SBATCH --job-name=arno_rpl7_final_eval
#SBATCH --partition=batch
#SBATCH --dependency=afterok:78463:78464
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/evaluation_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/evaluation_%j.err
set -euo pipefail
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation/evaluate.py"
