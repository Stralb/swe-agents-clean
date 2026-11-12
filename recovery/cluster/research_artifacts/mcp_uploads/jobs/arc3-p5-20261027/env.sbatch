#!/bin/bash
#SBATCH --job-name=arc3-env
#SBATCH --partition=biggpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/env-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/env-%j.err
set -euo pipefail
mkdir -p out/gpu
python3 - <<'PY'
from pathlib import Path
import os,json
b=Path('/home-mscluster/astrauss')
roots=[b/'RL-ARC-AGI-3-Project',b/'arc26',b/'arc_rl_final_e012',b/'.conda/envs',b/'.venvs',b/'miniconda3/envs',b/'anaconda3/envs',b/'venvs',b/'envs']
d={'root_candidates':{},'project_launchers':{},'python_candidates':[]}
for root in roots:
 if not root.is_dir():continue
 d['root_candidates'][str(root)]=[x.name for x in root.iterdir()][:65]
for root in roots[:3]:
 if not root.is_dir():continue
 for pat in ['*slurm','*.sbatch','requirements*.txt','README*','run*.sh','*venv*','*conda*','scripts','src','code','configs']:
  for x in list(root.glob(pat))[:25]:
   if x.is_file():
    try:txt=x.read_text(errors='replace')[:20000]
    except OSError:continue
    lines=txt.splitlines()
    mentions=[(i+1,l[:260]) for i,l in enumerate(lines) if any(k in l.lower() for k in ['python','conda','venv','module load','torch','cuda','pip install','srun','sbatch'])]
    if mentions:d['project_launchers'][str(x.relative_to(b))]=mentions[:25]
for root in roots:
 if not root.is_dir():continue
 for sub in [root,root/'bin',root/'venv/bin',root/'.venv/bin',root/'env/bin',root/'miniconda3/bin',root/'anaconda3/bin']:
  for name in ['python','python3']:
   exe=sub/name
   if exe.exists():d['python_candidates'].append(str(exe))
for root in [b/'.conda/envs',b/'miniconda3/envs',b/'anaconda3/envs',b/'venvs',b/'envs']:
 if root.is_dir():
  for sub in list(root.iterdir())[:35]:
   x=sub/'bin/python'
   if x.exists():d['python_candidates'].append(str(x))
Path('out/gpu/env_inventory.json').write_text(json.dumps(d,indent=2))
print('PYTHONS',json.dumps(d['python_candidates']))
print('ROOTS',json.dumps({k:v[:30] for k,v in d['root_candidates'].items()}))
print('LAUNCHERS',json.dumps({k:v[:12] for k,v in d['project_launchers'].items()})[:15000])
PY
command -v module || true
command -v conda || true
command -v python || true
command -v python3 || true
