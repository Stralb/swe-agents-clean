#!/bin/bash
#SBATCH --job-name=fcdisc-coordinator
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00

cd "$REPO" || true
if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
  "$PYTHON_BIN" "$ANALYSIS_DIR/coordinator.py"
else
  python3 "$ANALYSIS_DIR/coordinator.py"
fi
