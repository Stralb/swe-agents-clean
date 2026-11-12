#!/bin/bash
R="$(readlink -f "$HOME/research_artifacts/full_corpus_deep_discovery_v2_1_LATEST" 2>/dev/null)"
echo "V21_RUNROOT=$R"
echo
echo "=== ACTIVE V2.1 JOBS ==="
squeue -u astrauss -o '%.18i %.10P %.32j %.10T %.10M %.6D %R' 2>/dev/null | grep -E 'JOBID|fcv21' || true
echo
echo "=== CHECKPOINTS ==="
for S in audit redundancy associations motifs templates temporal patterns stability catalog report; do
  printf '%-16s ' "$S"
  if [ -f "$R/checkpoints/$S.json" ]; then grep -o '"status": *"[^"]*"' "$R/checkpoints/$S.json" | head -1; else echo NOT_WRITTEN; fi
done
echo
echo "=== FINAL STATUS ==="
cat "$R/00_audit/FINAL_STATUS_V21.json" 2>/dev/null || echo FINAL_STATUS_NOT_READY
echo
echo "=== REPORT ==="
ls -lh "$R/V2_1_DISCOVERY_REPORT.md" 2>/dev/null || echo REPORT_NOT_READY
