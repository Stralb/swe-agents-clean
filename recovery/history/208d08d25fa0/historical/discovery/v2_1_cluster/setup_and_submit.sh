#!/bin/bash
ANALYSIS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
PYTHON_BIN="$REPO/.venv/bin/python"
SOURCE_RUNROOT="$(readlink -f "$HOME/research_artifacts/full_corpus_deep_discovery_v2_LATEST" 2>/dev/null)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
V21_RUNROOT="$HOME/research_artifacts/full_corpus_deep_discovery_v2_1_${STAMP}"
mkdir -p "$V21_RUNROOT/logs" "$V21_RUNROOT/checkpoints" "$V21_RUNROOT/00_audit" || true
ln -sfn "$V21_RUNROOT" "$HOME/research_artifacts/full_corpus_deep_discovery_v2_1_LATEST" || true

echo "SOURCE_RUNROOT=$SOURCE_RUNROOT"
echo "V21_RUNROOT=$V21_RUNROOT"
echo "ANALYSIS_DIR=$ANALYSIS_DIR"

PRECHECK_OK=YES
if "$PYTHON_BIN" - "$SOURCE_RUNROOT" <<'PY'
import json,sys
from pathlib import Path
r=Path(sys.argv[1]);p=r/"00_manifest"/"FINAL_STATUS_V2.json"
if not p.exists(): raise RuntimeError("SOURCE_FINAL_STATUS_MISSING")
x=json.loads(p.read_text())
if x.get("status")!="PASS" or x.get("deep_discovery_complete") is not True or x.get("outcome_overlay_performed") is not False or x.get("security_outcomes_read") is not False:
    raise RuntimeError(f"SOURCE_V2_NOT_SAFE={x}")
print("SOURCE_V2_STATUS=PASS")
PY
then
  echo "SOURCE_PRECHECK=PASS"
else
  PRECHECK_OK=NO
  echo "SOURCE_PRECHECK=FAIL"
fi

if "$PYTHON_BIN" -m py_compile "$ANALYSIS_DIR"/v21_common.py "$ANALYSIS_DIR"/v21_analysis.py "$ANALYSIS_DIR"/v21_runner.py "$ANALYSIS_DIR"/coordinator.py; then
  echo "CODE_PREFLIGHT=PASS"
else
  PRECHECK_OK=NO
  echo "CODE_PREFLIGHT=FAIL"
fi

if "$PYTHON_BIN" "$ANALYSIS_DIR/self_test.py"; then
  echo "METHODOLOGY_SELF_TEST=PASS"
else
  PRECHECK_OK=NO
  echo "METHODOLOGY_SELF_TEST=FAIL"
fi

if [ "$PRECHECK_OK" = "YES" ]; then
  COORD="$(sbatch --parsable --job-name=fcv21-coordinator --partition=batch --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=2G --time=00:20:00 --output="$V21_RUNROOT/logs/fcv21-coordinator-%j.out" --error="$V21_RUNROOT/logs/fcv21-coordinator-%j.err" --export="ALL,ANALYSIS_DIR=$ANALYSIS_DIR,SOURCE_RUNROOT=$SOURCE_RUNROOT,V21_RUNROOT=$V21_RUNROOT,PYTHON_BIN=$PYTHON_BIN" "$ANALYSIS_DIR/coordinator.slurm" 2>&1)"
  echo "V21_COORDINATOR=$COORD"
else
  echo "V21_SUBMISSION=BLOCKED_BY_PREFLIGHT"
fi
sleep 5
bash "$ANALYSIS_DIR/status.sh" || true
