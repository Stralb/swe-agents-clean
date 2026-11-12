#!/bin/bash
#SBATCH --job-name=e126dataset
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
BASE=$ROOT/e126_kaggle_submit_20261027
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo VERIFY_E126_ARTIFACT
python3 - "$BASE" <<'PY'
from pathlib import Path
import hashlib,json,sys
p=Path(sys.argv[1])
m=json.loads((p/'submission_manifest.json').read_text())
assert hashlib.sha256((p/'dataset/my_agent.py').read_bytes()).hexdigest()==m['source_sha256']
assert hashlib.sha256((p/'kernel/submission.ipynb').read_bytes()).hexdigest()==m['notebook_sha256']
meta=json.loads((p/'dataset/dataset-metadata.json').read_text())
assert meta['isPrivate'] is True
assert meta['licenses']==[{'name':'other'}]
print('E126_SOURCES_VERIFIED',flush=True)
PY
"$KG" datasets create -p "$BASE/dataset"
echo DATASET_CREATE_RETURNED
"$KG" datasets status arnostrauss/arc-agi-3-e126-hybrid-source-20261027
echo E126_DATASET_PUBLISHED
