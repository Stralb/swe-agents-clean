#!/bin/bash
set -euo pipefail

OUT="$1"

echo "HOST=$(hostname)"
echo "START=$(date -u +%FT%TZ)"
echo "OUT=$OUT"

mkdir -p "$OUT"

gh auth status

python3 \
  /home-mscluster/astrauss/c_root_census_v1_0/prepare_c_root_census.py \
  --audit /home-mscluster/astrauss/PROVENANCE_CLOSURE_STEP2_v1.0/STEP2_EVIDENCE_AUDIT_455.csv \
  --out "$OUT" \
  > "$OUT/prepare.stdout.log" \
  2> "$OUT/prepare.stderr.log"

echo
echo "=== QC ==="
cat "$OUT/C_CONTEXT_QC.json"

echo
echo "=== SUPPLEMENTS ==="
cat "$OUT/NEEDS_SUPPLEMENT.csv"

touch "$OUT/JOB_COMPLETE.ok"

echo
echo "END=$(date -u +%FT%TZ)"
