#!/bin/bash
set -euo pipefail
CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
HV="$CAL/historical_validation"
mkdir -p "$HV/logs" "$HV/results" "$HV/suites"
rm -f "$HV/results"/S5PAIR-*.csv "$HV/summary.out" "$HV/summary.err" "$HV/HISTORICAL_VALIDATION_SUMMARY.csv"
AID="$(sbatch --parsable "$HV/bundle/run_historical_validation.sbatch")"
SID="$(sbatch --parsable --dependency=afterok:$AID "$HV/bundle/run_summary.sbatch")"
echo "$AID" > "$HV/ARRAY_JOBID.txt"
echo "$SID" > "$HV/SUMMARY_JOBID.txt"
echo "ARRAY_JOBID=$AID"
echo "SUMMARY_JOBID=$SID"
