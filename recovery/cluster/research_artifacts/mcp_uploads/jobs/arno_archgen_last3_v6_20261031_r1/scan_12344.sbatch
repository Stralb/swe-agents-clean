#!/bin/bash
#SBATCH --job-name=AG12344
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:40:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/12344_job_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/12344_job_%j.err
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/evaluate_verified.py 12344
