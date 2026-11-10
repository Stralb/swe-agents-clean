#!/bin/bash
#SBATCH --job-name=step7-symmetric-context
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=6
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=/home-mscluster/astrauss/decision_level_step7_collector/step7_collect_%j.out
#SBATCH --error=/home-mscluster/astrauss/decision_level_step7_collector/step7_collect_%j.err

cd /home-mscluster/astrauss/decision_level_step7_collector || true

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/research_artifacts/DECISION_LEVEL_STEP7_EVIDENCE_${STAMP}"
CACHE="$HOME/research_artifacts/DECISION_LEVEL_STEP7_REPO_CACHE"
PACKAGE="$HOME/DECISION_LEVEL_STEP7_EVIDENCE_${STAMP}.tar.gz"

echo "============================================================"
echo "STEP 7 SYMMETRIC DECISION EVIDENCE"
echo "JOB_ID=$SLURM_JOB_ID"
echo "HOST=$(hostname)"
echo "START=$(date -u)"
echo "============================================================"

echo
echo "=== TOOLS ==="
python3 --version || true
git --version || true
gh --version | head -1 || true
gh auth status 2>&1 | head -20 || true

mkdir -p "$OUT" "$CACHE" || true

python3 collect_step7_evidence.py \
  --manifest STEP7_SYMMETRIC_EVIDENCE_MANIFEST_51.csv \
  --out "$OUT" \
  --cache "$CACHE"
RC=$?

echo
echo "COLLECT_RC=$RC"

if [ "$RC" -eq 0 ] && [ -f "$OUT/COLLECTION_SUMMARY.csv" ]; then
  echo
echo "=== QC ==="
  python3 - "$OUT/COLLECTION_SUMMARY.csv" <<'PY'
import csv,sys,json
p=sys.argv[1]
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
from collections import Counter
c=Counter(r.get('status','') for r in rows)
print(json.dumps({'rows':len(rows),'status_counts':c},default=dict,indent=2))
if len(rows)!=102:
    raise SystemExit(1)
PY
  QC=$?
  if [ "$QC" -eq 0 ]; then
    tar -czf "$PACKAGE" -C "$(dirname "$OUT")" "$(basename "$OUT")" || true
    if [ -f "$PACKAGE" ]; then
      echo "STATUS=SUCCESS"
      echo "OUTPUT_DIR=$OUT"
      echo "PACKAGE=$PACKAGE"
      ls -lh "$PACKAGE" || true
      sha256sum "$PACKAGE" || true
    else
      echo "STATUS=FAILED"
      echo "REASON=PACKAGE_NOT_CREATED"
    fi
  else
    echo "STATUS=FAILED"
    echo "REASON=QC_FAILED"
  fi
else
  echo "STATUS=FAILED"
  echo "REASON=COLLECTION_FAILED"
fi

echo "END=$(date -u)"
