#!/bin/bash
#SBATCH --job-name=cf_hist_sum
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/historical_validation/summary.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/historical_validation/summary.err
set -euo pipefail
HV="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium/historical_validation"
python3 "$HV/bundle/summarize_all.py" "$HV/results" "$HV/HISTORICAL_VALIDATION_SUMMARY.csv"
