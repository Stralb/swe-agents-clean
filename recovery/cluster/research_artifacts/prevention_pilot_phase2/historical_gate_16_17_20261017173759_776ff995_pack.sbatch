#!/bin/bash
#SBATCH --job-name=p2histpack
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histpack_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histpack_%j.err

# Slurm worker ONLY. Collects the four independent historical control outputs.
set -euo pipefail
umask 077
: "${GATE_JOBID:?Missing GATE_JOBID}"
[[ "$GATE_JOBID" =~ ^[0-9]+$ ]] || exit 2
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
DIR="historical_gate_16_17_job${GATE_JOBID}"
ARCHIVE="${ROOT}/${DIR}.tar.gz"
[ -d "${ROOT}/${DIR}" ] || { echo "MISSING_RESULTS_DIR ${DIR}"; exit 3; }
[ ! -e "$ARCHIVE" ] || { echo "REFUSE_OVERWRITE ${ARCHIVE}"; exit 4; }

# Include detailed SARIF and task logs; archive only this new Slurm array's outputs.
tar -czf "$ARCHIVE" -C "$ROOT" "$DIR"
sha256sum "$ARCHIVE"
ls -lh "$ARCHIVE"

# Task outcomes are published without hiding failures.
for rank in 16 17; do
  for arm in base head; do
    path="${ROOT}/${DIR}/rank_${rank}/${arm}/RESULT.json"
    if [ -f "$path" ]; then
      grep -m1 '"status"' "$path" || true
      grep -m1 '"total_rule_alerts"' "$path" || true
    else
      echo "MISSING_RESULT rank=${rank} arm=${arm}"
    fi
  done
done

echo "ARCHIVE_READY $ARCHIVE"
