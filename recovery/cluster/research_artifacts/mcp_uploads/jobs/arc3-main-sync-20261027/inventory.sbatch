#!/bin/bash
#SBATCH --job-name=arc3-srcinventory
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/inventory-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/inventory-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -euo pipefail
mkdir -p evidence
python3 - <<'PY'
from pathlib import Path
import os,json,subprocess,hashlib,re
b=Path('/home-mscluster/astrauss')
roots=['RL-ARC-AGI-3-Project','arc_rl_final_e012','arc_rl_mechanics_killtest','e078_course_recovery']
patterns=['src','tests','scripts','configs','kaggle']
doc={'projects':{},'git':{}}
for name in roots:
 p=b/name
 if not p.is_dir():continue
 entry={'top_level':[x.name for x in p.iterdir() if x.name not in ['.venv','venv','.git']][:90], 'code':[]}
 for candidate in patterns:
  t=p/candidate
  if not t.exists():continue
  n=0
  for f in sorted(t.rglob('*')):
   if not f.is_file() or f.suffix not in ['.py','.json','.toml','.yaml','.yml','.slurm','.sh','.md','.txt']:continue
   if any(s in f.parts for s in ['.git','.venv','venv','__pycache__']):continue
   rel=str(f.relative_to(p))
   try:data=f.read_bytes()
   except OSError:continue
   entry['code'].append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
   n+=1
   if n>=180:break
 doc['projects'][name]=entry
 if (p/'.git').exists():
  def git(*args):
   try:
    x=subprocess.run(['git','-C',str(p),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=9,text=True)
    return x.stdout.strip()[:2000] if x.returncode==0 else 'ERROR:'+x.stderr[:140]
   except Exception as e:return 'ERROR:'+str(e)[:140]
  remote=git('remote','get-url','origin')
  remote=re.sub(r'(?i)(https?://)[^/@ ]+@',r'\1REDACTED@',remote)
  doc['git'][name]={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'remote':remote,'status':git('status','--short'),'tracked_neural':git('ls-files','src','kaggle','configs','tests','scripts')[:4000]}
Path('evidence/source_inventory.json').write_text(json.dumps(doc,indent=2))
for name,v in doc['projects'].items():
 print('PROJECT',name,'TOP',json.dumps(v['top_level'][:35]),'CODE_FILES',len(v['code']))
 print('SOURCES',json.dumps([x['path'] for x in v['code'] if x['path'].endswith('.py')][:75]))
print('GIT',json.dumps(doc['git']))
PY
