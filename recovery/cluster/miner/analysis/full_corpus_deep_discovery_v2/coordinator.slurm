#!/bin/bash
#SBATCH --job-name=fcdeep-coordinator
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00

cd "$REPO" || true
"$PYTHON_BIN" "$ANALYSIS_DIR/coordinator.py"
