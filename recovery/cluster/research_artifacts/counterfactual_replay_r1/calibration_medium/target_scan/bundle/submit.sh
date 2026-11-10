#!/bin/bash
set -euo pipefail
CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
B="$CAL/target_scan/bundle"
mkdir -p "$CAL/target_scan/logs" "$CAL/target_scan/results" "$CAL/target_scan/base_cache" "$CAL/target_scan/suites"
AID="$(sbatch --parsable "$B/run_target_scan.sbatch")"
SID="$(sbatch --parsable --dependency=afterok:$AID "$B/run_summary.sbatch")"
printf 'ARRAY_JOB=%s\nSUMMARY_JOB=%s\n' "$AID" "$SID" | tee "$CAL/target_scan/JOB_IDS.txt"
squeue -j "$AID,$SID"
