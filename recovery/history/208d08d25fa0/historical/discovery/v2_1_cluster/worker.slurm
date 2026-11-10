#!/bin/bash
cd "$ANALYSIS_DIR" || true
"$PYTHON_BIN" "$ANALYSIS_DIR/run_stage.py"
