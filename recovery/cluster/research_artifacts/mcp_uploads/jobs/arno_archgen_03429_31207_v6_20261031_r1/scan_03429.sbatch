#!/bin/bash
#SBATCH --job-name=ARCHGEN03429
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/03429_scan_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/03429_scan_%j.err
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/scan.py 03429
