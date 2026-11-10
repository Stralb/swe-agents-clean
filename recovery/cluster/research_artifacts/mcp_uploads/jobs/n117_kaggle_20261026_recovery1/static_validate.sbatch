#!/bin/bash
#SBATCH --job-name=arc3n117recoverystatic
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_recovery1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
python3 - <<'PY'
import ast,hashlib,json
from pathlib import Path
base=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_recovery1/kernel')
nb=json.loads((base/'submission.ipynb').read_text())
assert len(nb['cells'])==5
src=''.join(nb['cells'][3]['source'])
compile(src,'recovery_gateway_cell','exec')
tree=ast.parse(src)
values=[n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='init_source' for t in n.targets) and isinstance(n.value,ast.Constant)]
assert len(values)==1
compile(values[0],'agents_init.py','exec')
assert 'BoundedSemaphore(12)' in values[0]
assert 'record=True,' in src and 'record=False,' in src
assert 'gateway:8001/api/games' in src
assert 'KAGGLE_IS_COMPETITION_RERUN' in src
agent=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
assert hashlib.sha256(agent.read_bytes()).hexdigest()=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
meta=json.loads((base/'kernel-metadata.json').read_text())
assert meta['id']=='arnostrauss/arc-agi-3-n117-recovery-20261026'
assert meta['dataset_sources']==['arnostrauss/arc-agi-3-n117-agent-source-20261026']
assert meta['competition_sources']==['arc-prize-2026-arc-agi-3']
assert not meta['enable_internet']
print('RECOVERY_RUNTIME_WRAPPER_SYNTAX_OK')
print('RECOVERY_SLIMMED_FRAMEWORK_SYNTAX_OK')
print('SOURCE_AND_DATASET_MAPPING_OK')
print('NO_LIVE_API_CREDENTIALS_IN_NOTEBOOK')
PY
test -s /home-mscluster/astrauss/.kaggle/access_token
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < /home-mscluster/astrauss/.kaggle/access_token)"
mkdir -m 700 "$BASE/kaggle_home_status"
export HOME="$BASE/kaggle_home_status"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo 'SUBMISSION_STATUS'
"$ROOT/.venv/bin/kaggle" competitions submission 57675023
