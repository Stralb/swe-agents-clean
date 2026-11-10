#!/bin/bash
set -euo pipefail

RUNROOT="$1"

cd "$RUNROOT"

echo "HOST=$(hostname)"
echo "TIME=$(date -u +%FT%TZ)"

echo
echo "=== SELECTION ==="
cat C_SELECTION.json

echo
echo "=== FINAL QC ==="
cat final_selected/C_CONTEXT_QC.json

echo
echo "=== SUPPLEMENT FILE ==="
cat final_selected/NEEDS_SUPPLEMENT.csv

echo
echo "=== HASH ==="
sha256sum -c C_STAGE1_FINAL_READY.tar.gz.sha256

echo
echo "=== REQUIRED FILES ==="
ls -lh \
  final_selected/C_CODER_A_BLIND.tar.gz \
  final_selected/C_CODER_B_BLIND.tar.gz \
  final_selected/C_PRIVATE_MAPPING_DO_NOT_GIVE_CODERS.tar.gz \
  final_selected/AUTO_SINGLETON_ROOTS.csv

echo
echo "=== FINAL PACKAGE ==="
ls -lh \
  /home-mscluster/astrauss/C_STAGE1_FINAL_READY_LATEST.tar.gz \
  /home-mscluster/astrauss/C_STAGE1_FINAL_READY_LATEST.tar.gz.sha256

echo
echo "C_STAGE1_FINAL_AUDIT=PASS"
