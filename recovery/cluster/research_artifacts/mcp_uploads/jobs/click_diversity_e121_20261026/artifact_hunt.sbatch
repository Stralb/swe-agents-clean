#!/bin/bash
#SBATCH --job-name=e121hunt
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
targets=[p for p in root.iterdir() if p.is_dir() and (p.name.startswith(('e074','e075','e078','e079','e080','e101','n117_')))]
print('TARGETS',len(targets),flush=True)
for t in targets:
  matches=[]
  for d,dirs,files in os.walk(t):
    depth=len(Path(d).relative_to(t).parts)
    if depth>5:dirs[:]=[]
    dirs[:]=[z for z in dirs if z not in ('environment_files','site-packages','.venv','__pycache__','logs','node_modules','cache')]
    for f in files:
      if f=='replay_native.py' or f=='run_native.py' or f=='N100_ACTIVE_FSM_20261025.zip' or f=='arcengine' or f=='submission.py' or f.endswith(('.zip','.sif')) or 'arc' in f.lower() and f.endswith(('.json','.py')):
        fp=Path(d)/f
        matches.append((str(fp.relative_to(t)),fp.stat().st_size))
  if matches:
    print('TARGET',t.name,'MATCHES',len(matches),flush=True)
    for a,b in matches[:55]:print(' ',a,b,flush=True)
PY
python3 - <<'PY'
for pkg in ('numpy','scipy','torch','arcengine','arc_agi'):
 try:
  m=__import__(pkg);print('MODULE',pkg,'YES',getattr(m,'__version__','unknown'),flush=True)
 except Exception as e:print('MODULE',pkg,'NO',type(e).__name__,str(e)[:120],flush=True)
PY