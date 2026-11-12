#!/bin/bash
#SBATCH --job-name=fcdisc-v2-coordinator
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00

cd "$REPO" || true

if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
  "$PYTHON_BIN" "$ANALYSIS_DIR/mixed_phase_coordinator_v2.py"
else
  python3 "$ANALYSIS_DIR/mixed_phase_coordinator_v2.py"
fi
