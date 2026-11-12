#!/bin/bash
#SBATCH --job-name=arc3n117v2prepare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
python3 - <<'PY'
import json,hashlib
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
src=root/'n117_kaggle_20261026_dataset1/compact_kernel'
out=root/'n117_kaggle_20261026_v2/kernel'
out.mkdir(parents=True,exist_ok=True)
raw=(src/'submission.ipynb').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='a5bcc25d1f297185278877c0ea3dfc826baa2b294d55a97ae754d428b8823e64'
original=json.loads(raw)
nb=json.loads(raw)
install='''import os
import subprocess
import sys
from pathlib import Path

if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
    wheel_dir = Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels")
    if not wheel_dir.is_dir():
        raise RuntimeError("Competition wheel directory unavailable during rerun")
    subprocess.run(
        [sys.executable,"-m","pip","install","--no-index","--find-links",str(wheel_dir),"arc-agi","python-dotenv"],
        check=True,
    )
else:
    print("Commit mode: skipping competition-only dependency installation")
'''
assert len(nb['cells'])==5 and nb['cells'][1]['cell_type']=='code'
assert 'pip install' in ''.join(nb['cells'][1]['source'])
compile(install,'install.py','exec')
nb['cells'][1]['source']=install.splitlines(keepends=True)
nb['cells'][1]['outputs']=[]
nb['cells'][1]['execution_count']=None
assert all(nb['cells'][i]==original['cells'][i] for i in (0,2,3,4))
meta=json.loads((src/'kernel-metadata.json').read_text())
assert meta['id']=='arnostrauss/arc-agi-3-n117-local-effect-20261026'
assert meta['dataset_sources']==['arnostrauss/arc-agi-3-n117-agent-source-20261026']
agent=root/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
assert hashlib.sha256(agent.read_bytes()).hexdigest()=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
(out/'submission.ipynb').write_text(json.dumps(nb,ensure_ascii=False,separators=(',',':')))
(out/'kernel-metadata.json').write_text(json.dumps(meta,indent=2))
print('V2_BYTES', (out/'submission.ipynb').stat().st_size)
print('V2_SHA256',hashlib.sha256((out/'submission.ipynb').read_bytes()).hexdigest())
print('FROZEN_AGENT_SHA256_OK')
print('OTHER_CELLS_UNCHANGED')
PY