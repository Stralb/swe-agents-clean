#!/bin/bash
#SBATCH --job-name=arc3-recover
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/slurm-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/slurm-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import os,sys,json,hashlib,importlib.util
from pathlib import Path
home=Path.home()
names=['e078_course_recovery','arc_rl_final_e012','arc_phase3n_multigame','arc_rl_persistence_e007','arc_rl_final_e128','arc_rl_coursework','arc_rl_final_e079']
base=Path('/home-mscluster/astrauss')
roots=[]
for name in names:
 p=base/name
 if p.exists() and p.is_dir(): roots.append(p)
entry={'host':os.uname().nodename,'user':os.getenv('USER'),'python':sys.version.split()[0],'cwd':os.getcwd(),'root_exists':{},'candidates':[],'modules':{},'cwd_write':False}
for name in names: entry['root_exists'][name]=(base/name).is_dir()
for name in ['torch','numpy','gymnasium','arc_agi','arcengine','stable_baselines3']:
 try: entry['modules'][name]=importlib.util.find_spec(name) is not None
 except (ImportError,ValueError,AttributeError): entry['modules'][name]=False
try:
 p=Path('out/write_ok.txt');p.write_text('ok\n');entry['cwd_write']=True
except Exception as e:entry['write_error']=str(e)
patterns=('.py','.ipynb','.json','.csv','.pt','.pth','.ckpt','.sbatch','.log','.md')
for root in roots:
 visited=0
 try:
  for p in root.rglob('*'):
   visited+=1
   if visited>18000:break
   if not p.is_file() or p.suffix.lower() not in patterns:continue
   rel=str(p.relative_to(root))
   low=rel.lower()
   weight=sum(w in low for w in ('dqn','ppo','train','eval','trace','rollout','checkpoint','result','run','agent','policy','config'))
   if weight<1:continue
   try: stat=p.stat();size=stat.st_size
   except OSError:continue
   entry['candidates'].append({'root':root.name,'relative':rel,'bytes':size,'signal':weight})
 except (PermissionError,OSError) as exc:entry.setdefault('scan_errors',[]).append(str(exc))
 entry.setdefault('visited',{})[root.name]=visited
entry['candidates'].sort(key=lambda x:(-x['signal'],x['root'],x['relative']))
entry['candidates']=entry['candidates'][:500]
Path('out/recovery_manifest.json').write_text(json.dumps(entry,indent=2))
Path('out/candidate_files.tsv').write_text('root\trelative\tbytes\tsignal\n'+''.join('%s\t%s\t%d\t%d\n'%(r['root'],r['relative'],r['bytes'],r['signal']) for r in entry['candidates']))
print('ARC3_RECOVERY_JOB_COMPLETE')
print('ROOTS',json.dumps(entry['root_exists']))
print('MODULES',json.dumps(entry['modules']))
print('CANDIDATES',len(entry['candidates']))
print('TOP',json.dumps(entry['candidates'][:12]))
PY
