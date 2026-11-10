#!/bin/bash
#SBATCH --job-name=e121seedanalysis
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
python3 -m py_compile "$BASE/analyze_seeds.py"
python3 "$BASE/analyze_seeds.py"
echo E121_FINAL_PACKAGE_COMPLETE
