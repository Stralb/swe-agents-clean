#!/bin/bash
CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
BUNDLE="$CAL/corrected_target_eval_bundle_v1"
EVAL_OUT="$CAL/corrected_target_eval_v1"
export CAL EVAL_OUT
mkdir -p "$EVAL_OUT/run_results" "$EVAL_OUT/sarif" "$EVAL_OUT/cache" || true

echo "=== PREFLIGHT: discovering frozen run mapping, exact bases, and 16 generated patches ==="
python3 "$BUNDLE/prepare_manifest.py" "$EVAL_OUT"
RC=$?
if [ "$RC" -ne 0 ]; then
  echo
  echo "PREFLIGHT FAILED - no CodeQL jobs submitted. Send me the output above."
else
  echo
  echo "=== SUBMITTING 4-PAIR ARRAY ON batch, MAX 2 CONCURRENT ==="
  ARRAY_JOB="$(sbatch --parsable "$BUNDLE/run_pair.sbatch")"
  echo "ARRAY_JOB=$ARRAY_JOB"
  AGG_JOB="$(sbatch --parsable --dependency=afterany:$ARRAY_JOB "$BUNDLE/aggregate.sbatch")"
  echo "AGG_JOB=$AGG_JOB"
  printf '%s\n' "$ARRAY_JOB" > "$EVAL_OUT/ARRAY_JOBID.txt"
  printf '%s\n' "$AGG_JOB" > "$EVAL_OUT/AGG_JOBID.txt"
  echo
  echo "CHECK WITH:"
  echo "squeue -j $ARRAY_JOB,$AGG_JOB"
  echo
  echo "WHEN DONE:"
  echo "cat $EVAL_OUT/SUMMARY.txt"
  echo "cat $EVAL_OUT/SHA256SUMS.txt"
fi
