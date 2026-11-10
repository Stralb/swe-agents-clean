#!/bin/bash
set -euo pipefail
ROOT="$HOME/research_artifacts/counterfactual_replay_r1/codeql_diag_3581"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT"
cp "$HERE/diagnose.sbatch" "$ROOT/diagnose.sbatch"
JOBID="$(sbatch --parsable "$ROOT/diagnose.sbatch")"
echo "$JOBID" > "$ROOT/JOBID.txt"
echo "JOBID=$JOBID"
echo "When finished, run: cat $ROOT/summary.out"
