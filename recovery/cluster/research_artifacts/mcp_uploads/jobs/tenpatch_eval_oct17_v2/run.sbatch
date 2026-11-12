#!/bin/bash
#SBATCH --job-name=p2Seven
#SBATCH --partition=batch
#SBATCH --array=0-6
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=00:45:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import os,subprocess,json,pathlib,zipfile,tempfile,hashlib
home=pathlib.Path.home()/'research_artifacts'
root=home/'prevention_pilot_phase2'
names=['8147_O2','8147_P2','8147_W2','13922','9992','10779','3340']
sources=['screen5_blind_batch_job70117']*3+['next_wave5_blind_discovery_job70186']*4
packets=['CASE_03_8147.zip']*3+['CASE_01_13922.zip','CASE_02_09992.zip','CASE_03_10779.zip','CASE_04_03340.zip']
chunks=[['8147_O2.txt'],['8147_P2.txt'],['8147_W2.txt'],['13922.txt'],['9992.txt'],['10779.txt'],['3340_part0.txt','3340_part1.txt','3340_part2.txt']]
i=int(os.environ['SLURM_ARRAY_TASK_ID']);name=names[i]
out=root/('seven_eval_'+name+'_job'+os.environ['SLURM_JOB_ID']);out.mkdir()
state={'case':name,'state':'START','checks':{}}
def save(): (out/'RESULT.json').write_text(json.dumps(state,indent=2)+'\n')
def run(key,cmd,cwd=None):
 with (out/(key+'.log')).open('w') as f:
  r=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=2100)
 state['checks'][key]=r.returncode;save();return r.returncode==0
try:
 stage=home/'mcp_uploads/phase2_ten_20261017'
 patch=out/'candidate.patch';patch.write_bytes(b''.join((stage/k).read_bytes() for k in chunks[i]))
 temp=pathlib.Path(tempfile.mkdtemp(prefix='caseeval_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 with zipfile.ZipFile(root/sources[i]/packets[i]) as z:
  for x in z.infolist():
   if not x.filename.startswith('REPO/') or x.is_dir():continue
   if '..' in pathlib.PurePosixPath(x.filename).parts:raise ValueError('Bad path')
   t=temp/x.filename;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(z.read(x))
 repo=temp/'REPO'
 if not run('apply_check',['git','apply','--check',patch],repo):
  state['state']='NONAPPLY';save();raise SystemExit(0)
 run('apply',['git','apply',patch],repo)
 bin=home.parent/'tools/codeql/codeql'
 for label,folder in [('original',temp/'REPO'),('changed',repo)]:
  if label=='original':continue
  if not run('db',[bin,'database','create',out/'db','--language=javascript-typescript','--build-mode=none','--source-root='+str(folder),'--threads=2','--ram=8192'],folder):raise RuntimeError('db')
  if not run('scan',[bin,'database','analyze',out/'db','codeql/javascript-queries:codeql-suites/javascript-security-extended.qls','--format=sarif-latest','--output',out/'scan.sarif','--threads=2','--ram=8192'],folder):raise RuntimeError('scan')
 state['state']='SCAN_DONE'
except Exception as e:state['state']='ERROR';state['error']=str(e)
save()
PY