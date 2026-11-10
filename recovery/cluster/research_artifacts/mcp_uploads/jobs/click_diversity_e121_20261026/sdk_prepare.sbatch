#!/bin/bash
#SBATCH --job-name=e121prepare_sdk
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
mkdir -p "$BASE/runtime"
echo '=== PYTHON ENV CANDIDATES ==='
for py in /usr/bin/python3 /home-mscluster/astrauss/arc26/.venv_cuda130/bin/python /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/python /home-mscluster/astrauss/.venv/bin/python; do
 if test -x "$py"; then
  echo "PYTHON $py"
  "$py" -c "import importlib.util,sys; print(sys.version.split()[0], {x:bool(importlib.util.find_spec(x)) for x in ('numpy','scipy','torch','arcengine','arc_agi')})" || true
 fi
done
echo '=== SOURCE INTERFACE ==='
python3 - <<'PY'
import ast,hashlib
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
data=p.read_bytes();s=data.decode().splitlines()
print('SOURCE_HASH',hashlib.sha256(data).hexdigest())
t=ast.parse(data)
for x in t.body:
 if isinstance(x,ast.ClassDef) and x.name in ('MyAgent','PortableAgentCore','PretrainedPUCTCore','AuditedCrossLevelCore'):
  print('\n=== CLASS',x.name,x.lineno,x.end_lineno,'===')
  for y in x.body:
   if isinstance(y,(ast.FunctionDef,ast.AsyncFunctionDef)):
    print('METHOD',y.name,y.lineno,y.end_lineno)
  if x.name=='MyAgent':
   for i in range(x.lineno-1,min(x.lineno+70,x.end_lineno)):
    print(i+1,s[i][:190])
PY
echo '=== KAGGLE COMPETITION DATA DOWNLOAD ==='
CLI=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/api_home"
export HOME="$BASE/api_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$CLI" competitions download -c arc-prize-2026-arc-agi-3 -p "$BASE/runtime"
echo '=== ARCHIVE FILES ==='
find "$BASE/runtime" -maxdepth 1 -type f -printf '%f %s bytes\n'
echo DONE
