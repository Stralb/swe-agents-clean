#!/usr/bin/env bash

main() {
  echo "HOST=$(hostname)"
  echo "JOB_ID=${SLURM_JOB_ID:-NA}"
  echo "STAGE=${STAGE:-}"
  echo "OUTROOT=${OUTROOT:-}"
  echo "SOURCE_RUNROOT=${SOURCE_RUNROOT:-}"
  echo "PYTHON_BIN=${PYTHON_BIN:-}"

  if [ -z "${STAGE:-}" ] || [ -z "${OUTROOT:-}" ] || [ -z "${SOURCE_RUNROOT:-}" ] || [ -z "${PYTHON_BIN:-}" ] || [ -z "${ANALYSIS_DIR:-}" ]; then
    echo "WORKER_PREFLIGHT=FAIL missing environment variable"
    return 2
  fi

  mkdir -p "$OUTROOT/logs" "$OUTROOT/checkpoints" || true

  "$PYTHON_BIN" "$ANALYSIS_DIR/v22_discovery.py" \
    --stage "$STAGE" \
    --outroot "$OUTROOT" \
    --source "$SOURCE_RUNROOT"
  RC=$?

  echo "WORKER_STAGE=$STAGE"
  echo "WORKER_RC=$RC"
  return "$RC"
}

main "$@"
