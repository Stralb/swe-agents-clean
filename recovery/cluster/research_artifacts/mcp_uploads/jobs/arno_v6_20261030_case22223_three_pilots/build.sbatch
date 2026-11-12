#!/bin/bash
#SBATCH --job-name=arno_3pilot_pack
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/build_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/build_%j.err
set -euo pipefail
umask 077
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/build.py"
python3 -u "$HOME/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/build.py"
