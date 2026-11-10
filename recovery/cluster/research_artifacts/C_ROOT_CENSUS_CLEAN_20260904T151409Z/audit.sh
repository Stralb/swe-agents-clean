#!/bin/bash
set -euo pipefail

RUNROOT="$1"

cd "$RUNROOT"

echo "=== SELECTION ==="
cat C_SELECTION.json

echo
echo "=== QC ==="
cat final_selected/C_CONTEXT_QC.json

echo
echo "=== SUPPLEMENTS ==="
cat final_selected/NEEDS_SUPPLEMENT.csv

echo
echo "=== HASH ==="
sha256sum -c C_STAGE1_CLEAN_READY.tar.gz.sha256

echo
echo "=== CONTENTS ==="
tar -tzf C_STAGE1_CLEAN_READY.tar.gz | head -100

echo
echo "=== READY FILE ==="
ls -lh \
  /home-mscluster/astrauss/C_STAGE1_CLEAN_READY_LATEST.tar.gz \
  /home-mscluster/astrauss/C_STAGE1_CLEAN_READY_LATEST.tar.gz.sha256

echo
echo "C_STAGE1_FINAL_AUDIT=PASS"
