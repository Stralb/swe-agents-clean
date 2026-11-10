#!/bin/bash
#SBATCH --job-name=arno_v3_r3
#SBATCH --partition=bigbatch
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=arno_v3_r3_%j.log
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_replay_sidecar_v3_20261101"
python3 -B fix_count_and_path_r3.py
python3 -B sidecar_build_r3.py
python3 -B sidecar_build_r3.py --execute
echo ARNO_SIDECAR_V3_R3_COMPLETED
