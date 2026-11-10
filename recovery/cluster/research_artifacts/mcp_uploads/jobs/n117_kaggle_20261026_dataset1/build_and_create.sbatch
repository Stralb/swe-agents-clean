#!/bin/bash
#SBATCH --job-name=arc3n117dataset
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
mkdir -p "$OUT/private_dataset" "$OUT/compact_kernel" "$OUT/isolated_home"
python3 - <<'PY'
import json,hashlib
from pathlib import Path
root=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work")
out=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1")
raw=(root/"kaggle_kernel/submission.ipynb").read_bytes()
assert hashlib.sha256(raw).hexdigest()=="0f049935a633a14ba82c0427386e5eef852f3a8972aa205b61a3ca0e70c01acd"
nb=json.loads(raw)
cell=nb['cells'][2]
assert cell['cell_type']=='code'
source=''.join(cell['source'])
assert source.startswith('%%writefile /tmp/my_agent.py\n')
source=source.partition('\n')[2]
compile(source,"my_agent.py","exec")
payload=source.encode('utf-8')
agent_hash=hashlib.sha256(payload).hexdigest()
dataset=out/"private_dataset"
(dataset/"my_agent.py").write_bytes(payload)
(dataset/"dataset-metadata.json").write_text(json.dumps({
"id":"arnostrauss/arc-agi-3-n117-agent-source-20261026",
"title":"ARC AGI 3 N117 Agent Source 20261026",
"subtitle":"Private frozen agent source for the ARC AGI 3 Kaggle notebook",
"description":"Private, all-rights-reserved N117 agent source and embedded model checkpoint. Attached to the competition notebook to avoid its 1 MB source limit. No changes to agent logic.",
"licenses":[{"name":"copyright-authors"}]
},indent=2))
dataset_ref="arnostrauss/arc-agi-3-n117-agent-source-20261026"
new_source=(
"from pathlib import Path\n"
"import hashlib\n"
"files = [p for p in Path('/kaggle/input').rglob('my_agent.py') if 'arc-agi-3-n117-agent-source-20261026' in str(p)]\n"
"if len(files) != 1:\n    raise RuntimeError(f'N117 agent dataset missing or ambiguous: {len(files)} matches')\n"
"data = files[0].read_bytes()\n"
f"if hashlib.sha256(data).hexdigest() != {agent_hash!r}:\n    raise RuntimeError('Frozen N117 source SHA256 mismatch')\n"
"Path('/tmp/my_agent.py').write_bytes(data)\n"
"print('Frozen N117 agent source verified and installed')\n"
)
cell['source']=new_source.splitlines(keepends=True)
cell['outputs']=[]
cell['execution_count']=None
meta=json.loads((root/"kaggle_kernel/kernel-metadata.json").read_text())
meta['dataset_sources']=[dataset_ref]
compact=out/"compact_kernel"
(compact/"kernel-metadata.json").write_text(json.dumps(meta,indent=2))
(compact/"submission.ipynb").write_text(json.dumps(nb,ensure_ascii=False,separators=(',',':')))
new_raw=(compact/"submission.ipynb").read_bytes()
assert len(new_raw)<900000,len(new_raw)
assert nb['cells'][3]['source']==json.loads(raw)['cells'][3]['source']
print('AGENT_BYTES',len(payload))
print('AGENT_SHA256',agent_hash)
print('COMPACT_NOTEBOOK_BYTES',len(new_raw))
print('COMPACT_NOTEBOOK_SHA256',hashlib.sha256(new_raw).hexdigest())
print('DATASET_REF',dataset_ref)
PY
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
export HOME="$OUT/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" datasets create -p "$OUT/private_dataset"
echo DATASET_CREATE_SENT
"$ROOT/.venv/bin/kaggle" datasets status arnostrauss/arc-agi-3-n117-agent-source-20261026
echo DATASET_STATUS_QUERIED
