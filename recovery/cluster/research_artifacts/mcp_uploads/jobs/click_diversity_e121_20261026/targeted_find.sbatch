#!/bin/bash
#SBATCH --job-name=e121runtimefind
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
import os,ast
root=Path('/home-mscluster/astrauss')
special=['e093_from_reset_research','e095_from_reset_research','RL-ARC-AGI-3-Project','arc26','e074_human_training','E074_HUMAN_TO_POLICY_20261019']
for target in special:
 p=root/target
 if not p.is_dir():continue
 print('ROOT',p,flush=True)
 for dirpath,dirs,files in os.walk(p):
  depth=len(Path(dirpath).relative_to(p).parts)
  if depth>=5:dirs[:]=[]
  dirs[:]=[x for x in dirs if x not in ('environment_files','.git','node_modules','site-packages','.venv','venv','artifacts','logs','results','__pycache__','data')]
  for name in files:
   if name in ('N100_ACTIVE_FSM_20261025.zip','replay_native.py','run_native.py','submission.py','run_public_games.py','requirements.txt','n090.py','ARC-AGI-3-Agents-main.zip') or ('N1' in name and name.endswith('.zip')):
    fp=Path(dirpath)/name
    print('FILE',fp,fp.stat().st_size,flush=True)
  if depth<=2:print('DIR',dirpath,'subdirs',','.join(dirs[:20]),flush=True)
q=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
t=ast.parse(q.read_text());src=q.read_text().splitlines()
for n in t.body:
 if isinstance(n,ast.ClassDef) and n.name=='MyAgent':
  print('AGENT_CLASS',n.lineno,n.end_lineno,flush=True)
  print('\n'.join(str(i+1)+': '+src[i][:175] for i in range(n.lineno-1,min(n.end_lineno,n.lineno+80))),flush=True)
PY