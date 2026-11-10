#!/bin/bash
#SBATCH --job-name=e121analysis
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
python3 -m py_compile "$BASE/analyze_e121_v2.py"
python3 "$BASE/analyze_e121_v2.py"
echo E121_EVIDENCE_ANALYSIS_COMPLETE
