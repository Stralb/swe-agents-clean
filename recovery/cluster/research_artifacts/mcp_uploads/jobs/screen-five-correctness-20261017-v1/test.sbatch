#!/bin/bash
#SBATCH --job-name=screen5funct
#SBATCH --partition=batch
#SBATCH --array=0-1
#SBATCH --cpus-per-task=2
#SBATCH --mem=5G
#SBATCH --time=00:14:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path,PurePosixPath
import os,json,zipfile,hashlib,subprocess,tempfile,shutil
cases=[(8147,3,'src/agent/file-mentions.test.ts','file_mention'),(15686,4,'src/lib/__tests__/github-token.test.ts','github_token')]
id,order,test,label=cases[int(os.environ['SLURM_ARRAY_TASK_ID'])]
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
source=root/'screen5_blind_batch_job70117'/('CASE_%02d_%d.zip'%(order,id))
previous_job=70128 if id==8147 else 70129
patch=root/('screen5_eval_%d_job%d'%(id,previous_job))/'generated.patch'
out=root/('screen5_func_%d_job%s'%(id,os.environ['SLURM_JOB_ID']));out.mkdir(exist_ok=True)
data={'id':id,'state':'STARTED','checks':{}}
def save(): (out/'RESULT.json').write_text(json.dumps(data,indent=2)+'\n')
def run(n,cmd,dir,t=300):
 with (out/(n+'.log')).open('w') as log:
  try:
   v=subprocess.run(list(map(str,cmd)),cwd=dir,stdout=log,stderr=subprocess.STDOUT,timeout=t)
   data['checks'][n]={'returncode':v.returncode}
  except Exception as e:data['checks'][n]={'error':repr(e)[:400]}
  save()
  return data['checks'][n].get('returncode')==0
try:
 tmp=Path(tempfile.mkdtemp(prefix='funct_%d_'%id,dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 dest=tmp/'REPO';dest.mkdir()
 with zipfile.ZipFile(source) as z:
  for info in z.infolist():
   if not info.filename.startswith('REPO/') or info.is_dir():continue
   if (info.external_attr>>16)&0o170000==0o120000:continue
   pieces=PurePosixPath(info.filename).parts
   assert '..' not in pieces
   f=tmp/info.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(info))
 assert run('patch',['git','apply','--check',patch],dest,60)
 assert run('apply',['git','apply',patch],dest,60)
 data['package_scripts']=json.loads((dest/'package.json').read_text()).get('scripts',{})
 bun=str(Path.home()/'.bun/bin/bun')
 deps=dest/'node_modules'
 if not deps.exists():
  run('install',[bun,'install','--ignore-scripts','--frozen-lockfile'],dest,500)
 if deps.exists():
  run('targeted_test',[bun,'x','vitest','run',test],dest,240)
  run('typecheck',[bun,'x','tsc','--noEmit'],dest,330)
 data['state']='COMPLETE'
except Exception as e:data['state']='ERROR';data['error']=repr(e)
save()
print(json.dumps(data)[:2600],flush=True)
PY
