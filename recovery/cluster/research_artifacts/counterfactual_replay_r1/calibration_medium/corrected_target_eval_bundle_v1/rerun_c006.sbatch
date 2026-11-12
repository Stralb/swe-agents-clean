#!/bin/bash
#SBATCH --job-name=cf_C006
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --output=cf_C006_%j.out
#SBATCH --error=cf_C006_%j.err

CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
EVAL_OUT="$CAL/corrected_target_eval_v1"
BUNDLE="$CAL/corrected_target_eval_bundle_v1"

export CAL EVAL_OUT
export RUN_ONLY=C006
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"

python3 "$BUNDLE/evaluate_pair.py" S5PAIR-016
