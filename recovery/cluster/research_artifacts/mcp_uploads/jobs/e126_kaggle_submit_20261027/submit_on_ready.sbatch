#!/bin/bash
#SBATCH --job-name=e126submit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:50:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
BASE=$ROOT/e126_kaggle_submit_20261027
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
KERNEL=arnostrauss/arc-agi-3-e126-hybrid-20261027
DATASET=arnostrauss/arc-agi-3-e126-hybrid-source-20261027
echo E126_KAGGLE_DATASET_STATUS
"$KG" datasets status "$DATASET"
echo E126_WAIT_KERNEL_COMMIT
READY=0
for i in $(seq 1 100); do
  STATUS=$("$KG" kernels status "$KERNEL")
  echo "E126_KERNEL_POLL_$i $STATUS"
  if [[ "$STATUS" == *COMPLETE* ]]; then READY=1;break;fi
  if [[ "$STATUS" == *ERROR* || "$STATUS" == *CANCEL* || "$STATUS" == *FAIL* ]];then
    echo E126_KERNEL_FAILED;exit 12
  fi
  sleep 15
done
if [[ "$READY" != 1 ]];then echo E126_COMMIT_NOT_READY;exit 13;fi
echo E126_COMMIT_COMPLETE
mkdir -p "$BASE/commit_output"
"$KG" kernels output "$KERNEL" -p "$BASE/commit_output"
test -s "$BASE/commit_output/submission.parquet"
echo E126_PREVIEW_PARQUET_CONFIRMED
python3 - "$BASE" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
m=json.loads((p/'submission_manifest.json').read_text())
assert m['source_sha256']=='84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c'
assert hashlib.sha256((p/'kernel/submission.ipynb').read_bytes()).hexdigest()==m['notebook_sha256']
assert m['kernel_id']=='arnostrauss/arc-agi-3-e126-hybrid-20261027'
print('E126_FINAL_SOURCE_AND_VERSION_CHECKS_OK')
PY
echo E126_EXISTING_SUBMISSIONS
OLD=$("$KG" competitions submissions -c arc-prize-2026-arc-agi-3)
echo "$OLD" | head -15
if printf '%s' "$OLD" | grep -q 'E126 hybrid trained source verified'; then
  echo E126_ALREADY_SUBMITTED;exit 0
fi
echo E126_SUBMIT_KAGGLE_COMPETITION
"$KG" competitions submit arc-prize-2026-arc-agi-3 -f submission.parquet -k "$KERNEL" -v 1 -m "E126 hybrid trained source verified; N117 plus click contingency and pretrained sparse-scene effect prior"
echo E126_OFFICIAL_SUBMISSION_REQUEST_ACCEPTED
"$KG" competitions submissions -c arc-prize-2026-arc-agi-3 | head -18
echo E126_SUBMIT_STAGE_COMPLETE
