#!/bin/bash
#SBATCH --job-name=arno_AC12_v6
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --array=0-11%3
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/scan_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/scan_%A_%a.err
set -euo pipefail
umask 077
CASES=(32759 08152 03429 03581 12344 31207)
INDEX=$((SLURM_ARRAY_TASK_ID / 2))
if (( SLURM_ARRAY_TASK_ID % 2 == 0 )); then ARM=A; else ARM=C; fi
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/scan_case.py "${CASES[$INDEX]}" "$ARM"
