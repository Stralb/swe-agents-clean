#!/bin/bash
#SBATCH --job-name=cf_cal_sum
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/target_scan/summary.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/target_scan/summary.err
set -euo pipefail
CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
python3 "$CAL/target_scan/bundle/summarize_all.py"
