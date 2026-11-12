#!/usr/bin/env bash

main() {
  ANALYSIS_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
  REPO="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
  PYTHON_BIN="$REPO/.venv/bin/python"
  SOURCE_RUNROOT="${SOURCE_RUNROOT:-/home-mscluster/astrauss/research_artifacts/full_corpus_deep_discovery_v2_20260829T181912Z}"
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  OUTROOT="$HOME/research_artifacts/full_corpus_deep_discovery_v2_2_$STAMP"
  LATEST="$HOME/research_artifacts/full_corpus_deep_discovery_v2_2_LATEST"

  echo "============================================================"
  echo "FULL-CORPUS CHANGE-OPERATION DISCOVERY V2.2"
  echo "============================================================"
  echo "ANALYSIS_DIR=$ANALYSIS_DIR"
  echo "SOURCE_RUNROOT=$SOURCE_RUNROOT"
  echo "OUTROOT=$OUTROOT"
  echo "PYTHON_BIN=$PYTHON_BIN"

  if [ ! -x "$PYTHON_BIN" ]; then
    echo "PREFLIGHT=FAIL missing Python: $PYTHON_BIN"
    return 2
  fi
  if [ ! -d "$SOURCE_RUNROOT" ]; then
    echo "PREFLIGHT=FAIL missing frozen v2 source runroot: $SOURCE_RUNROOT"
    return 2
  fi
  if [ ! -f "$SOURCE_RUNROOT/00_manifest/FINAL_STATUS_V2.json" ]; then
    echo "PREFLIGHT=FAIL missing v2 final status"
    return 2
  fi

  echo
  echo "=== OUTCOME-BLIND SOURCE CHECK ==="
  "$PYTHON_BIN" - "$SOURCE_RUNROOT" <<'PY'
import json, sys
from pathlib import Path
r=Path(sys.argv[1])
x=json.loads((r/'00_manifest'/'FINAL_STATUS_V2.json').read_text())
print('source_status=',x.get('status'))
print('deep_discovery_complete=',x.get('deep_discovery_complete'))
print('security_outcomes_read=',x.get('security_outcomes_read'))
print('outcome_overlay_performed=',x.get('outcome_overlay_performed'))
if x.get('status')!='PASS' or x.get('security_outcomes_read') is not False or x.get('outcome_overlay_performed') is not False:
    raise SystemExit('SOURCE_NOT_CLEAN_OUTCOME_BLIND_V2')
PY
  if [ $? -ne 0 ]; then
    echo "PREFLIGHT=FAIL source outcome-blinding invariant"
    return 2
  fi

  echo
  echo "=== PYTHON DEPENDENCIES ==="
  "$PYTHON_BIN" - <<'PY'
mods=['numpy','pandas','scipy','pyarrow','tabulate']
failed=[]
for m in mods:
    try:
        x=__import__(m)
        print('IMPORT_OK',m,getattr(x,'__version__',''))
    except Exception as e:
        print('IMPORT_FAIL',m,repr(e)); failed.append(m)
if failed:
    raise SystemExit('MISSING=' + ','.join(failed))
PY
  if [ $? -ne 0 ]; then
    echo "PREFLIGHT=FAIL missing dependency"
    return 2
  fi

  echo
  echo "=== SYNTAX CHECK ==="
  "$PYTHON_BIN" -m py_compile \
    "$ANALYSIS_DIR/v22_common.py" \
    "$ANALYSIS_DIR/v22_discovery.py" \
    "$ANALYSIS_DIR/coordinator.py"
  if [ $? -ne 0 ]; then
    echo "PREFLIGHT=FAIL syntax"
    return 2
  fi
  echo "SYNTAX_CHECK=PASS"

  mkdir -p "$OUTROOT/logs" "$OUTROOT/checkpoints" "$OUTROOT/00_audit" || true
  cp "$ANALYSIS_DIR/README_METHOD.md" "$OUTROOT/README_METHOD.md" 2>/dev/null || true
  cp "$ANALYSIS_DIR/V2_2_SPEC.md" "$OUTROOT/V2_2_SPEC.md" 2>/dev/null || true
  ln -sfn "$OUTROOT" "$LATEST" || true

  echo
  echo "=== SUBMIT COORDINATOR ==="
  COORD="$({ sbatch --parsable \
    --job-name=fcv22-coordinator \
    --partition=batch \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=1 \
    --mem=2G \
    --time=00:20:00 \
    --output="$OUTROOT/logs/fcv22-coordinator-%j.out" \
    --error="$OUTROOT/logs/fcv22-coordinator-%j.err" \
    --export="ALL,ANALYSIS_DIR=$ANALYSIS_DIR,OUTROOT=$OUTROOT,SOURCE_RUNROOT=$SOURCE_RUNROOT,PYTHON_BIN=$PYTHON_BIN" \
    "$ANALYSIS_DIR/coordinator.slurm"; } 2>&1)"
  RC=$?
  echo "COORDINATOR_SUBMIT_RC=$RC"
  echo "COORDINATOR_JOB=$COORD"
  if [ $RC -ne 0 ]; then
    echo "SUBMISSION=FAIL"
    return "$RC"
  fi

  sleep 5
  echo
  "$ANALYSIS_DIR/status.sh" || true
  return 0
}

main "$@"
