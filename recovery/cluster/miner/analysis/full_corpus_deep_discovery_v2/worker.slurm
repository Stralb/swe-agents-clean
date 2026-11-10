#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1

cd "$REPO" || true

if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
  "$PYTHON_BIN" "$ANALYSIS_DIR/run_stage.py"
else
  python3 "$ANALYSIS_DIR/run_stage.py"
fi
