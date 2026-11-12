#!/bin/bash
#SBATCH --job-name=c3882full
#SBATCH --partition=batch
#SBATCH --array=0-1%2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=22G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/c3882full_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/c3882full_%A_%a.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import hashlib, io, json, os, pathlib, re, subprocess, tarfile, time, urllib.request
from pathlib import Path

root = Path.home() / 'research_artifacts' / 'prevention_pilot_phase2'
job = os.environ['SLURM_ARRAY_JOB_ID']
index = int(os.environ['SLURM_ARRAY_TASK_ID'])
assert index in (0,1)
arm = ('before', 'historical_pr')[index]
commit = ('5789f89a3f6bed8a9f40447a73e75b81b277b1c8','c53cfcd19d46d23f621c60dcc4d074814d417a59')[index]
repo = 'LibreChat-AI/LibreChat'
target_file = 'packages/api/src/artifacts/update.ts'
rule = 'js/polynomial-redos'
out = root / ('case3882_full_reproduction_job' + job) / arm
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Refusing to reuse nonempty result directory'
scratch = Path(os.environ.get('SLURM_TMPDIR') or '/tmp') / ('case3882_full_' + job + '_' + arm)
scratch.mkdir(parents=True, exist_ok=False)
src = scratch / 'repo'
src.mkdir()
codeql = Path.home() / 'tools/codeql/codeql'
query = Path.home() / '.codeql/packages/codeql/javascript-queries/2.3.11/Performance/PolynomialReDoS.ql'
assert codeql.is_file() and query.is_file()
def sha256_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
def save(data):
 (out/'RESULT.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
report={'case_id':3882,'arm':arm,'repository':repo,'commit_sha':commit,'historical_pr_number':14121,'target_rule':rule,'target_file':target_file,'query_path':str(query),'query_sha256':sha256_file(query),'codeql_binary':str(codeql),'status':'STARTED'}
save(report)
url='https://codeload.github.com/'+repo+'/tar.gz/'+commit
tar=scratch/'snapshot.tar.gz'
for attempt in range(3):
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Wits-CAUSAL-3882-full-repository'})
  with urllib.request.urlopen(req,timeout=180) as inp,tar.open('wb') as output:
   size=0
   while True:
    chunk=inp.read(2**20)
    if not chunk:break
    size+=len(chunk)
    assert size<650_000_000,'Snapshot exceeds safety limit'
    output.write(chunk)
  break
 except Exception:
  if attempt==2:raise
  time.sleep(6)
report['snapshot_tar_sha256']=sha256_file(tar)
report['snapshot_tar_bytes']=tar.stat().st_size
save(report)
nfiles=0
total=0
with tarfile.open(tar,'r:gz') as archive:
 for member in archive:
  parts=pathlib.PurePosixPath(member.name).parts
  if len(parts)<2: continue
  rel=pathlib.PurePosixPath(*parts[1:])
  if rel.is_absolute() or '..' in rel.parts:continue
  dest=src.joinpath(*rel.parts)
  if member.isdir():
   dest.mkdir(parents=True,exist_ok=True)
  elif member.isfile():
   nfiles+=1
   total+=member.size
   assert nfiles<130_000 and total<2_500_000_000,'Snapshot extraction size cap'
   dest.parent.mkdir(parents=True,exist_ok=True)
   with archive.extractfile(member) as i, dest.open('xb') as o:
    while True:
     b=i.read(2**20)
     if not b:break
     o.write(b)
report['extracted_files']=nfiles
report['extracted_bytes']=total
assert (src/target_file).exists(), 'Historical target absent'
report['target_file_sha256']=sha256_file(src/target_file)
save(report)
def run(cmd,label,timeout):
 print('START',arm,label,flush=True)
 with (out/(label+'.log')).open('x') as fh:
  p=subprocess.run(list(map(str,cmd)),cwd=src,stdout=fh,stderr=subprocess.STDOUT,timeout=timeout)
 report[label+'_exit']=p.returncode
 save(report)
 print('END',arm,label,p.returncode,flush=True)
 if p.returncode:raise RuntimeError(label+' failed; see log')
run([codeql,'version'],'codeql_version',60)
db=scratch/'database'
run([codeql,'database','create',db,'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17500'],'database_create',4500)
sarif=out/'target_rule.sarif'
run([codeql,'database','analyze',db,query,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=17500'],'target_query',1800)
obj=json.loads(sarif.read_text())
hits=[]
for run in obj.get('runs',[]):
 for result in run.get('results',[]):
  if result.get('ruleId')!=rule:continue
  locs=[]
  for location in result.get('locations',[]):
   p=location.get('physicalLocation',{})
   locs.append({'file':p.get('artifactLocation',{}).get('uri'),'line':p.get('region',{}).get('startLine')})
  flows=[]
  for cf in result.get('codeFlows',[]):
   for thread in cf.get('threadFlows',[]):
    steps=[]
    for location in thread.get('locations',[]):
     point=location.get('location',{})
     phys=point.get('physicalLocation',{})
     steps.append({'file':phys.get('artifactLocation',{}).get('uri'),'line':phys.get('region',{}).get('startLine'),'description':point.get('message',{}).get('text')})
    flows.append(steps)
  hits.append({'locations':locs,'fingerprints':result.get('partialFingerprints',{}),'message':result.get('message',{}).get('text'),'code_flows':flows})
report['matching_rule_alerts']=len(hits)
report['target_file_alerts']=[x for x in hits if any(target_file in str(l['file']) for l in x['locations'])]
report['all_rule_alerts']=hits
report['status']='SCAN_COMPLETE'
save(report)
print('SCAN_COMPLETE',arm,'ALL_RULE',len(hits),'TARGET_FILE',len(report['target_file_alerts']),flush=True)
PY
