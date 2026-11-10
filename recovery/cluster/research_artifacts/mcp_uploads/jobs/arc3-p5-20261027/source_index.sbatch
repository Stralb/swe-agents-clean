#!/bin/bash
#SBATCH --job-name=arc3-src-index
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/source-index-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/source-index-%j.err
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os,json,subprocess
home=Path('/home-mscluster/astrauss')
roots=['RL-ARC-AGI-3-Project','e078_course_recovery','arc_rl_final_e012','arc_rl_mechanics_killtest']
skip={'.git','.venv','venv','env','node_modules','__pycache__','cache','.cache','checkpoints','outputs','frames','recordings','results','models','data','tmp','logs','unsloth_compiled_cache','wandb','.pytest_cache'}
out={'roots':{},'potential_code':[]}
for name in roots:
 r=home/name
 if not r.is_dir():continue
 top=sorted([p.name+('/' if p.is_dir() else '') for p in r.iterdir()])[:120]
 files=[]
 for wd,ds,fs in os.walk(r):
  dep=len(Path(wd).relative_to(r).parts)
  ds[:]=[d for d in ds if d not in skip and not d.startswith('.')]
  if dep>=6:ds[:]=[]
  for f in fs:
   p=Path(wd)/f
   if p.suffix.lower() not in ('.py','.ipynb','.json','.yaml','.yml','.toml','.md','.txt','.sh','.cfg','.ini','.lock'):continue
   if f.lower().endswith('.lock'):continue
   try:sz=p.stat().st_size
   except OSError:continue
   if sz>500000:continue
   rel=str(p.relative_to(r));low=rel.lower()
   score=4*any(t in low for t in ['dqn','ppo','train','agent','policy','runner','rollout','qnet','reinforce'])+2*any(t in low for t in ['config','test','replay','mask','native','suite','smoke','action','research'])
   files.append({'path':rel,'size':sz,'score':score})
   if len(files)>1200:break
  if len(files)>1200:break
 out['roots'][name]={'top':top,'files_total':len(files),'highlights':sorted(files,key=lambda x:(-x['score'],x['path']))[:120],'src_files':[x for x in files if x['path'].startswith('src/') or x['path'].startswith('tests/')][:300]}
 if (r/'.git').is_dir():
  try:
   st=subprocess.run(['git','-C',str(r),'remote','-v'],capture_output=True,text=True,timeout=4)
   out['roots'][name]['git_remotes']=[x.split()[1] for x in st.stdout.splitlines() if x.strip()][:5]
  except Exception:pass
outp=Path('out/source_index_20261027.json');outp.write_text(json.dumps(out,indent=2))
for name,v in out['roots'].items():
 print('PROJECT',name,'FILES',v['files_total'],'TOP',v['top'][:40])
 print('HIGHLIGHTS',json.dumps(v['highlights'][:42]))
 print('GIT',v.get('git_remotes'))
print('INDEX',outp.resolve())
PY