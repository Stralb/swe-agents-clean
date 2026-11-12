#!/bin/bash
#SBATCH --job-name=8147test3
#SBATCH --partition=batch
#SBATCH --array=0-2
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
export PATH="$HOME/.bun/bin:$HOME/tools/node/bin:$PATH"
python3 - <<'PY'
import os,zipfile,subprocess,tempfile,pathlib,json
r=pathlib.Path.home()/'research_artifacts'
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
names=['8147_O2','8147_P2','8147_W2']
o=r/'prevention_pilot_phase2'/('test8147_'+names[i]+'_job'+os.environ['SLURM_JOB_ID']);o.mkdir()
t=pathlib.Path(tempfile.mkdtemp(prefix='test8147_'))
with zipfile.ZipFile(r/'prevention_pilot_phase2/screen5_blind_batch_job70117/CASE_03_8147.zip') as z:
 for p in z.namelist():
  if p.startswith('REPO/') and not p.endswith('/'):
   q=t/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(z.read(p))
repo=t/'REPO'
patch=r/'mcp_uploads/phase2_ten_20261017'/(names[i]+'.txt')
out={}
for label,args,limit in [('apply',['git','apply',patch],50),('install',['bun','install','--frozen-lockfile','--ignore-scripts'],480),('test',['bun','x','vitest','run','src/agent/file-mentions.test.ts'],300),('typecheck',['bun','x','tsc','--noEmit'],360)]:
 try:
  with (o/(label+'.log')).open('w') as h:
   v=subprocess.run([str(x) for x in args],cwd=repo,stdout=h,stderr=subprocess.STDOUT,timeout=limit)
  out[label]=v.returncode
  if v.returncode!=0:break
 except Exception as e:out[label]=str(e)[:150];break
(o/'RESULT.json').write_text(json.dumps(out,indent=2))
print(names[i],out)
PY