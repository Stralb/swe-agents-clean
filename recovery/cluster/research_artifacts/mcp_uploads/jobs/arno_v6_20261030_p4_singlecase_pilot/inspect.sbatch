#!/bin/bash
#SBATCH --job-name=rpl7_p4_inspect
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p4_singlecase_pilot/inspect_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p4_singlecase_pilot/inspect_%j.err
set -euo pipefail
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p4_singlecase_pilot/inspect.py"
