#!/bin/bash
#SBATCH --job-name=e121preflight
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
python3 - <<'PY'
import os,sys,hashlib
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts')
print('PYTHON',sys.executable,sys.version.split()[0])
print('ROOT_TOP', sorted(x.name for x in root.iterdir())[:120])
target=['N100_ACTIVE_FSM_20261025.zip','N117','N114','FROZEN_B1_PRETRAINED_PUCT_KAGGLE_20261025.zip','arc_rl','sdk_runtime','replay_native.py','policy.py','run_native.py','FROZEN','n093']
found=[]
visited=0
for dirpath,dirs,files in os.walk(root):
    depth=len(Path(dirpath).relative_to(root).parts)
    if depth>9:
        dirs[:]=[]
        continue
    dirs[:]=[d for d in dirs if d not in ('node_modules','.git','.venv','venv','__pycache__','site-packages','environment_files','logs','images') and not d.startswith('.')]
    visited+=1
    for x in files:
        if (x=='N100_ACTIVE_FSM_20261025.zip' or x=='FROZEN_B1_PRETRAINED_PUCT_KAGGLE_20261025.zip' or x=='replay_native.py' or x=='run_native.py' or x=='policy.py' or ('N117' in x and (x.endswith('.zip') or x.endswith('.json')))):
            p=Path(dirpath)/x
            print('FOUND_FILE',p,'BYTES',p.stat().st_size,flush=True)
            found.append(str(p))
    for x in dirs:
        if x=='sdk_runtime' or x=='N100_ACTIVE_FSM' or x.startswith('N117') or x.startswith('n117') or x.startswith('n114'):
            p=Path(dirpath)/x
            if len(found)<180:
                print('FOUND_DIR',p,flush=True)
                found.append(str(p))
    if visited>50000:
        print('SCAN_LIMIT_REACHED');break
print('VISITED',visited,'FOUND',len(found))
for package in ('torch','numpy','scipy','arcengine','arc_agi','pytest'):
    try:
        mod=__import__(package)
        print('IMPORT',package,'OK',getattr(mod,'__version__','unknown'),getattr(mod,'__file__',''))
    except Exception as e:
        print('IMPORT',package,'FAIL',type(e).__name__,str(e)[:130])
src=root/'mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
assert src.is_file()
print('N117_SUBMITTED_SOURCE',src.stat().st_size,hashlib.sha256(src.read_bytes()).hexdigest())
PY