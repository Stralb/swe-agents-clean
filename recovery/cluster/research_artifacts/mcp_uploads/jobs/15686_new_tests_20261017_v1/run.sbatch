#!/bin/bash
#SBATCH --job-name=15686test2
#SBATCH --partition=batch
#SBATCH --array=0-1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
export PATH="$HOME/.bun/bin:$HOME/tools/node/bin:$PATH"
python3 - <<'PY'
import os,json,tempfile,pathlib,zipfile,subprocess
root=pathlib.Path.home()/'research_artifacts'
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
v=['15686_P2','15686_P3'][i]
parts=[['15686_P2_part0.txt','15686_P2_part1.txt'],['15686_P3.txt']][i]
test=['src/lib/__tests__/github-credentials.test.ts','src/lib/__tests__/github-fetch.test.ts'][i]
out=root/'prevention_pilot_phase2'/('tasktest_'+v+'_job'+os.environ['SLURM_JOB_ID']);out.mkdir()
tmp=pathlib.Path(tempfile.mkdtemp(prefix='gitstudy_'))
with zipfile.ZipFile(root/'prevention_pilot_phase2/screen5_blind_batch_job70117/CASE_04_15686.zip') as z:
 for n in z.namelist():
  if not n.startswith('REPO/') or n.endswith('/'):continue
  f=tmp/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(n))
repo=tmp/'REPO'
stage=root/'mcp_uploads/phase2_ten_20261017'
p=out/'p.patch';p.write_bytes(b''.join((stage/k).read_bytes() for k in parts))
status={}
for n,cmd,limit in [('apply',['git','apply',p],45),('install',['bun','install','--ignore-scripts','--frozen-lockfile'],600),('test',['bun','x','vitest','run',test],270),('typecheck',['bun','x','tsc','--noEmit'],400)]:
 try:
  with (out/(n+'.log')).open('w') as f:q=subprocess.run([str(x) for x in cmd],cwd=repo,stdout=f,stderr=subprocess.STDOUT,timeout=limit)
  status[n]=q.returncode
  if q.returncode:break
 except Exception as e:status[n]=repr(e)[:130];break
(out/'RESULT.json').write_text(json.dumps(status,indent=2)+'\n')
print(v,status,flush=True)
PY