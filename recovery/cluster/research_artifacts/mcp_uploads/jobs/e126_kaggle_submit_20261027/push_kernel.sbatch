#!/bin/bash
#SBATCH --job-name=e126kernel
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
BASE=$ROOT/e126_kaggle_submit_20261027
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo CHECK_DATASET
"$KG" datasets status arnostrauss/arc-agi-3-e126-hybrid-source-20261027
echo VERIFY_KERNEL
python3 - "$BASE" <<'PY'
import json,hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads((p/'submission_manifest.json').read_text())
assert hashlib.sha256((p/'kernel/submission.ipynb').read_bytes()).hexdigest()==m['notebook_sha256']
nb=json.loads((p/'kernel/submission.ipynb').read_text())
assert nb['metadata']['kaggle']['isInternetEnabled']==False
meta=json.loads((p/'kernel/kernel-metadata.json').read_text())
assert meta['id']==m['kernel_id']
assert meta['dataset_sources']==[m['dataset_id']]
assert meta['competition_sources']==['arc-prize-2026-arc-agi-3']
print('E126_NOTEBOOK_CHECKS_OK')
PY
echo PUSH_E126_NOTEBOOK
"$KG" kernels push -p "$BASE/kernel"
echo PUSH_E126_NOTEBOOK_COMPLETE
"$KG" kernels status arnostrauss/arc-agi-3-e126-hybrid-20261027
echo E126_KERNEL_STATUS_REQUESTED
