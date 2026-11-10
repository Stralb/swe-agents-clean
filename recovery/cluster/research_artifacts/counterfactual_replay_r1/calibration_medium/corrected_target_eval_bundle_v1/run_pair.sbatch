#!/bin/bash
#SBATCH --job-name=cf_tgtfix
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --array=0-3%2
#SBATCH --output=%x_%A_%a.out
#SBATCH --error=%x_%A_%a.err

CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
EVAL_OUT="$CAL/corrected_target_eval_v1"
BUNDLE="$CAL/corrected_target_eval_bundle_v1"
export CAL EVAL_OUT
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"

PAIRS=(S5PAIR-001 S5PAIR-016 S5PAIR-025 S5PAIR-044)
PAIR="${PAIRS[$SLURM_ARRAY_TASK_ID]}"

echo "PAIR=$PAIR"
echo "HOST=$(hostname)"
"$HOME/tools/codeql/codeql" version | head -1
python3 "$BUNDLE/evaluate_pair.py" "$PAIR"
