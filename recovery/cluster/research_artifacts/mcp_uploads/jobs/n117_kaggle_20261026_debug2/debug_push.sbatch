#!/bin/bash
#SBATCH --job-name=arc3n117kdebug
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
WORK="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
NOTEBOOK="$WORK/kaggle_kernel/submission.ipynb"
test -s "$TOKEN"
test "$(sha256sum "$NOTEBOOK" | awk '{print $1}')" = "0f049935a633a14ba82c0427386e5eef852f3a8972aa205b61a3ca0e70c01acd"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
RUNHOME="$WORK/kaggle_isolated_debug2"
mkdir -m 700 "$RUNHOME"
export HOME="$RUNHOME"
export XDG_CONFIG_HOME="$RUNHOME/.config"
export KAGGLE_CONFIG_DIR="$RUNHOME/.config/kaggle"
"$WORK/.venv/bin/python" - <<'PY'
import re
from kaggle.api.kaggle_api_extended import KaggleApi
api=KaggleApi()
api.authenticate()
print('KAGGLE_AUTH_INIT_OK', flush=True)
try:
    kernels=api.kernels_list(mine=True, page=1)
    print('KERNEL_LIST_OK', len(kernels), flush=True)
except Exception as e:
    print('KERNEL_LIST_ERROR', type(e).__name__, flush=True)
try:
    response=api.kernels_push('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/kaggle_kernel')
    print('KERNEL_PUSH_SUCCESS', str(response)[:600], flush=True)
except Exception as e:
    print('KERNEL_PUSH_EXCEPTION_CLASS', type(e).__name__, flush=True)
    body=getattr(getattr(e, 'response', None), 'text', '') or str(e)
    body=re.sub(r'KGAT_[A-Za-z0-9]+', '[REDACTED_TOKEN]', body)
    print('KERNEL_PUSH_RESPONSE_BODY', body[:3000], flush=True)
PY
