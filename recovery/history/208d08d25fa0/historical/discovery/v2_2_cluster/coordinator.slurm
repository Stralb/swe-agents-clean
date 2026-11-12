#!/usr/bin/env bash

main() {
  echo "V22_COORDINATOR_HOST=$(hostname)"
  echo "V22_COORDINATOR_JOB=${SLURM_JOB_ID:-NA}"

  if [ -z "${ANALYSIS_DIR:-}" ] || [ -z "${OUTROOT:-}" ] || [ -z "${SOURCE_RUNROOT:-}" ] || [ -z "${PYTHON_BIN:-}" ]; then
    echo "V22_COORDINATOR_PREFLIGHT=FAIL"
    return 2
  fi

  mkdir -p "$OUTROOT/logs" "$OUTROOT/00_audit" || true
  "$PYTHON_BIN" "$ANALYSIS_DIR/coordinator.py"
  RC=$?
  echo "V22_COORDINATOR_RC=$RC"
  return "$RC"
}

main "$@"
