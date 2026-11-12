#!/bin/bash
cd "$ANALYSIS_DIR" || true
"$PYTHON_BIN" "$ANALYSIS_DIR/coordinator.py"
