#!/bin/bash
#SBATCH --job-name=arno_22223_3pilot_scan
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --array=0-2
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_case22223_three_pilot_scan/log_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_case22223_three_pilot_scan/log_%A_%a.err
set -euo pipefail
umask 077
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
ARMS=(A B C)
ARM="${ARMS[$SLURM_ARRAY_TASK_ID]}"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_case22223_three_pilot_scan/scan.py" --arm "$ARM"
