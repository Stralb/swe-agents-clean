#!/bin/bash
#SBATCH --job-name=e121compat
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
echo IMPORT_SPECS_BEFORE
"$PY" - <<'PY'
from importlib.util import find_spec
for n in ['torch','scipy','numpy','requests','pydantic','flask','dotenv','jinja2','markupsafe','werkzeug','click','certifi','idna','urllib3','charset_normalizer']:
 print(n, bool(find_spec(n)),flush=True)
PY
python3 - <<'PY'
from pathlib import Path
import zipfile,io
base=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
z=zipfile.ZipFile(base/'runtime/arc-prize-2026-arc-agi-3.zip')
site=base/'runtime/python_site'
modules=('blinker','click','flask','itsdangerous','jinja2','markupsafe','python_dotenv','werkzeug','requests','certifi','idna','urllib3')
wheels=[p for p in z.namelist() if p.startswith('arc_agi_3_wheels/') and p.endswith('.whl')]
for stem in modules:
 matches=[n for n in wheels if n.split('/')[-1].startswith(stem+'-')]
 assert len(matches)==1,(stem,matches)
 with zipfile.ZipFile(io.BytesIO(z.read(matches[0]))) as w:
  w.extractall(site)
 print('EXTRACTED',stem,flush=True)
PY
echo IMPORT_SDK
PYTHONPATH="$BASE/runtime/python_site" "$PY" - <<'PY'
from arc_agi import Arcade,OperationMode
from arcengine import GameAction,GameState
import pydantic,flask,torch,numpy,scipy
print('ALL_IMPORTS_OK',torch.__version__,numpy.__version__,pydantic.__version__,flush=True)
PY
echo SMOKE_RETRY
export PYTHONPATH="$BASE/runtime/python_site"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
"$PY" "$BASE/runtime_bootstrap.py" smoke
echo E121_SMOKE_COMPLETED
