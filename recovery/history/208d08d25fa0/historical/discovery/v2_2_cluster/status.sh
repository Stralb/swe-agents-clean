#!/usr/bin/env bash

RUNROOT="$(readlink -f "$HOME/research_artifacts/full_corpus_deep_discovery_v2_2_LATEST" 2>/dev/null)"
echo "V22_RUNROOT=$RUNROOT"

if [ -z "$RUNROOT" ] || [ ! -d "$RUNROOT" ]; then
  echo "V22_RUNROOT_NOT_FOUND"
  return 0 2>/dev/null || true
fi

echo
echo "=== ACTIVE V2.2 JOBS ==="
squeue -u astrauss -o '%.18i %.10P %.32j %.10T %.12M %.6D %R' 2>/dev/null | grep -E 'JOBID|fcv22' || true

echo
echo "=== CHECKPOINTS ==="
for STAGE in audit blocks transformations flows cochange templates validate catalog report
do
  printf '%-18s ' "$STAGE"
  if [ -f "$RUNROOT/checkpoints/$STAGE.json" ]; then
    grep -o '"status": *"[^"]*"' "$RUNROOT/checkpoints/$STAGE.json" | head -1 || true
  else
    echo "NOT_WRITTEN"
  fi
done

echo
echo "=== FINAL STATUS ==="
cat "$RUNROOT/00_audit/FINAL_STATUS_V22.json" 2>/dev/null || echo "FINAL_STATUS_NOT_WRITTEN"

echo
echo "=== SUBMITTED DAG ==="
cat "$RUNROOT/00_audit/SUBMITTED_JOBS_V22.json" 2>/dev/null || echo "DAG_MANIFEST_NOT_WRITTEN"

echo
echo "=== REPORT ==="
ls -lh "$RUNROOT/V2_2_DISCOVERY_REPORT.md" 2>/dev/null || echo "REPORT_NOT_READY"
