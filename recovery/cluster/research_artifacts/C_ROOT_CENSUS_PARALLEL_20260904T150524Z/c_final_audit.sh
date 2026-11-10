#!/bin/bash
set -euo pipefail

RUNROOT="$1"

echo "HOST=$(hostname)"
echo "TIME=$(date -u +%FT%TZ)"

echo
echo "=== SELECTION ==="
cat "$RUNROOT/C_SELECTION.json"

echo
echo "=== QC ==="
cat "$RUNROOT/final_selected/C_CONTEXT_QC.json"

echo
echo "=== ARCHIVE CONTENTS ==="
tar -tzf "$RUNROOT/C_STAGE1_READY.tar.gz"

echo
echo "=== HASH ==="
sha256sum -c "$RUNROOT/C_STAGE1_READY.tar.gz.sha256"

echo
echo "=== FINAL FILE ==="
ls -lh /home-mscluster/astrauss/C_STAGE1_READY_LATEST.tar.gz

echo
echo "C_STAGE1_AUDIT=PASS"
