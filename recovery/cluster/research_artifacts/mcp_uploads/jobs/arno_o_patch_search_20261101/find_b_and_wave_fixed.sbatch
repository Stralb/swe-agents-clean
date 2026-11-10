#!/bin/bash
#SBATCH --job-name=arno_find_b_wave_fix
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_o_patch_search_20261101"
python3 -B find_b_and_wave_fixed.py
