#!/bin/bash
#SBATCH --job-name=rpl7_comparison
#SBATCH --partition=batch
#SBATCH --dependency=afterok:78455
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation/summary_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation/summary_%j.err
set -euo pipefail
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation/evaluate.py"
