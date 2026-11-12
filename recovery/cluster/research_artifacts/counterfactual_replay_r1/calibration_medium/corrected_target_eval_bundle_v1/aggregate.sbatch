#!/bin/bash
#SBATCH --job-name=cf_tgtagg
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err

CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
EVAL_OUT="$CAL/corrected_target_eval_v1"
BUNDLE="$CAL/corrected_target_eval_bundle_v1"
python3 "$BUNDLE/aggregate.py" "$EVAL_OUT"
sha256sum "$EVAL_OUT/CORRECTED_TARGET_EVAL.csv" "$EVAL_OUT/SUMMARY.txt" > "$EVAL_OUT/SHA256SUMS.txt"
cat "$EVAL_OUT/SUMMARY.txt"
cat "$EVAL_OUT/SHA256SUMS.txt"
