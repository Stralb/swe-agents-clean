#!/bin/bash
#SBATCH --job-name=case3882full
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_full_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_full_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import hashlib,io,json,os,pathlib,re,shutil,subprocess,tarfile,time,urllib.request
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
job=os.environ['SLURM_JOB_ID']
out=root/('case3882_historical_fullscan_job'+job)
out.mkdir(parents=True,exist_ok=True)
assert not (out/'RESULT.json').exists(),'Refuse to overwrite'
scratch=pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('case3882_fullscan_'+job)
scratch.mkdir(parents=True,exist_ok=True)
assert not (scratch/'base').exists(), 'Scratch already used'
base='5789f89a3f6bed8a9f40447a73e75b81b277b1c8'
head='c53cfcd19d46d23f621c60dcc4d074814d417a59'
repo='LibreChat-AI/LibreChat'
rule='js/polynomial-redos'
target='packages/api/src/artifacts/update.ts'
codeql=pathlib.Path.home()/'tools/codeql/codeql'
pack=pathlib.Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11'
assert codeql.is_file() and pack.is_dir()
query=[]
for p in pack.rglob('*.ql'):
 try:hd=p.read_text(errors='replace')[:6000]
 except OSError:continue
 if re.search(r'(?m)^\s*\*?\s*@id\s+'+re.escape(rule)+r'\s*$',hd):query.append(p)
assert len(query)==1
query=query[0]
result={'case_id':3882,'pr':14121,'base_sha':base,'head_sha':head,'target_file':target,'target_rule':rule,'query_path':str(query),'scope':'FULL_REPOSITORY','arms':{}}
def fetch_commit(sha,label):
 url='https://codeload.github.com/'+repo+'/tar.gz/'+sha
 blob=None
 for _ in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-case3882-fullscan'})
   with urllib.request.urlopen(req,timeout=180) as resp:blob=resp.read(350000001)
   if len(blob)>350000000:raise RuntimeError('Archive size exceeds cap')
   break
  except Exception:
   time.sleep(3)
 if blob is None:raise RuntimeError(label+' archive fetch failed')
 source=scratch/label
 source.mkdir()
 with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as tf:
  for m in tf:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   if '..' in rel.parts:raise RuntimeError('Invalid archive path')
   dest=source.joinpath(*rel.parts)
   if m.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tf.extractfile(m) as f,dest.open('xb') as w:shutil.copyfileobj(f,w)
 print('FETCHED',label,len(blob),'bytes compressed',flush=True)
 return source,hashlib.sha256(blob).hexdigest()
def scan(sha,label):
 src,sha256=fetch_commit(sha,label)
 outarm={'tar_sha256':sha256}
 sourcefile=src/target
 assert sourcefile.exists(), 'Target file absent'
 outarm['target_sha256']=hashlib.sha256(sourcefile.read_bytes()).hexdigest()
 for step,cmd,timeout in [
  ('create',[codeql,'database','create',scratch/('db_'+label),'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=21000'],3000),
  ('analyze',[codeql,'database','analyze',scratch/('db_'+label),query,'--format=sarif-latest','--output='+str(out/(label+'.sarif')),'--threads=4','--ram=21000'],2300)
 ]:
  print('RUN',label,step,flush=True)
  try:p=subprocess.run(list(map(str,cmd)),cwd=src,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=timeout)
  except subprocess.TimeoutExpired as e:raise RuntimeError(label+' '+step+' TIMEOUT') from e
  (out/(label+'_'+step+'.log')).write_text(p.stdout)
  outarm[step+'_exit']=p.returncode
  print('END',label,step,p.returncode,flush=True)
  if p.returncode:raise RuntimeError(label+' '+step+' failed '+p.stdout[-750:])
 obj=json.loads((out/(label+'.sarif')).read_text())
 findings=[]
 for run in obj.get('runs',[]):
  for item in run.get('results',[]):
   if item.get('ruleId')!=rule:continue
   ls=[]
   for loc in item.get('locations',[]):
    pl=loc.get('physicalLocation',{})
    ls.append({'file':pl.get('artifactLocation',{}).get('uri'),'line':pl.get('region',{}).get('startLine')})
   findings.append({'locations':ls,'fingerprints':item.get('partialFingerprints',{})})
 outarm['rule_findings']=len(findings)
 outarm['target_file_findings']=[x for x in findings if any(str(l['file']).endswith(target) for l in x['locations'])]
 outarm['findings']=findings
 result['arms'][label]=outarm
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
 print('RESULT',label,'total',len(findings),'target_file',len(outarm['target_file_findings']),flush=True)
scan(base,'base')
scan(head,'historical_head')
result['verdict']='ELIGIBLE_MATCHING_RULE_INTRODUCED' if not result['arms']['base']['target_file_findings'] and result['arms']['historical_head']['target_file_findings'] else 'NOT_VALIDATED_AS_INTRODUCTION'
(out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print('FINAL',result['verdict'],flush=True)
PY
