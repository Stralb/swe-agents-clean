#!/bin/bash
#SBATCH --job-name=arnoAC9solo
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --array=0-8%3
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$PATH"
CASES=(32759 32759 08152 03581 03581 12344 12344 31207 31207)
ARMS=(A C C A C A C A C)
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/scan_case_solo_v3.py "${CASES[$SLURM_ARRAY_TASK_ID]}" "${ARMS[$SLURM_ARRAY_TASK_ID]}"
