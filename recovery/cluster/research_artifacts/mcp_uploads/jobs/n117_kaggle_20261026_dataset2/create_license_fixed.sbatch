#!/bin/bash
#SBATCH --job-name=arc3n117dsfix
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/dataset-metadata.json")
m=json.loads(p.read_text())
assert m['id']=="arnostrauss/arc-agi-3-n117-agent-source-20261026"
m['licenses']=[{'name':'other'}]
m['description']+=" All source rights retained by authors; private Kaggle dataset."
p.write_text(json.dumps(m,indent=2))
print("DATASET_METADATA_LICENSE_SET_TO_OTHER")
PY
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$OUT/isolated_fix_home"
export HOME="$OUT/isolated_fix_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" datasets create -p "$OUT/private_dataset"
echo DATASET_CREATE_RETURNED
"$ROOT/.venv/bin/kaggle" datasets status arnostrauss/arc-agi-3-n117-agent-source-20261026
echo DATASET_STATUS_RETURNED
