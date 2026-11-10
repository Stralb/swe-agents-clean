#!/bin/bash
#SBATCH --job-name=p2Three
#SBATCH --partition=batch
#SBATCH --array=0-2
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=00:45:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import os,subprocess,json,pathlib,zipfile,tempfile,hashlib
home=pathlib.Path.home()/'research_artifacts'
root=home/'prevention_pilot_phase2'
names=['15686_P2','15686_P3','313']
sources=['screen5_blind_batch_job70117']*2+['next_wave5_blind_discovery_job70186']
packets=['CASE_04_15686.zip']*2+['CASE_05_00313.zip']
chunks=[['15686_P2_part0.txt','15686_P2_part1.txt'],['15686_P3.txt'],['313.txt']]
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
 baseline=temp/'BASE'
 import shutil
 shutil.copytree(repo,baseline)
 if not run('apply_check',['git','apply','--check',patch],repo):
  state['state']='NONAPPLY';save();raise SystemExit(0)
 run('apply',['git','apply',patch],repo)
 bin=home.parent/'tools/codeql/codeql'
 for label,folder in [('original',baseline),('changed',repo)]:
  db=out/('db_'+label)
  if not run('db_'+label,[bin,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(folder),'--threads=2','--ram=8192'],folder):raise RuntimeError('db')
  if not run('scan_'+label,[bin,'database','analyze',db,'codeql/javascript-queries:codeql-suites/javascript-security-extended.qls','--format=sarif-latest','--output',out/(label+'.sarif'),'--threads=2','--ram=8192'],folder):raise RuntimeError('scan')
 def findings(label):
  a=json.loads((out/(label+'.sarif')).read_text());rows=[]
  for rr in a.get('runs',[]):
   for v in rr.get('results',[]):
    loc=(v.get('locations') or [{}])[0].get('physicalLocation',{});fp=v.get('partialFingerprints') or {}
    rows.append({'rule':v.get('ruleId'),'path':loc.get('artifactLocation',{}).get('uri'),'line':loc.get('region',{}).get('startLine'),'message':v.get('message',{}).get('text'),'fp':fp})
  return rows
 before= findings('original')
 after=findings('changed')
 from collections import Counter
 def key(v):return(v['rule'],v['path'],v['fp'].get('primaryLocationLineHash') or v['message'],v['fp'].get('primaryLocationStartColumnFingerprint') or '')
 b=Counter(map(key,before));new=[]
 for v in after:
  k=key(v)
  if b[k]:b[k]-=1
  else:new.append(v)
 state['all_rules']={'before':len(before),'after':len(after),'introduced':len(new),'by_rule':dict(Counter(v['rule'] for v in new)),'findings':[{'rule':v['rule'],'path':v['path'],'line':v['line']} for v in new]}
 state['state']='SCAN_DONE'
except Exception as e:state['state']='ERROR';state['error']=str(e)
save()
PY