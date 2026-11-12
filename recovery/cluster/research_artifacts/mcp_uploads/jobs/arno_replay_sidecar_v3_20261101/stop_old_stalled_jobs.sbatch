#!/bin/bash
#SBATCH --job-name=arno_stop_superseded
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
set -euo pipefail
for item in "79728:arno_v3_r3" "79732:arno_sidecar_local"; do
 jobid="${item%%:*}"
 expected="${item#*:}"
 actual="$(squeue --noheader --jobs="$jobid" --format="%j" | head -n 1 | tr -d ' ')"
 if [ "$actual" = "$expected" ]; then
  scancel "$jobid"
  echo "Cancelled superseded job $jobid ($expected); output files preserved"
 else
  echo "Skipped $jobid: active name '$actual' did not match '$expected'"
 fi
done
