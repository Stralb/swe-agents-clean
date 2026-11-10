#!/bin/bash
#SBATCH --job-name=case3882prescan
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_prescan_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_prescan_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import hashlib,json,os,pathlib,re,subprocess,time,urllib.request
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
job=os.environ['SLURM_JOB_ID']
out=root/('case3882_historical_prescan_job'+job)
out.mkdir(parents=True,exist_ok=False)
scratch=pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('case3882_prescan_'+job)
scratch.mkdir(parents=True,exist_ok=False)
base='5789f89a3f6bed8a9f40447a73e75b81b277b1c8'
head='c53cfcd19d46d23f621c60dcc4d074814d417a59'
path='packages/api/src/artifacts/update.ts'
repository='LibreChat-AI/LibreChat'
codeql=pathlib.Path.home()/'tools/codeql/codeql'
pack=pathlib.Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11'
assert codeql.is_file() and pack.is_dir()
rule='js/polynomial-redos'
candidates=[]
for p in pack.rglob('*.ql'):
 try: header=p.read_text(errors='replace')[:6000]
 except OSError: continue
 if re.search(r'(?m)^\s*\*?\s*@id\s+'+re.escape(rule)+r'\s*$',header):candidates.append(p)
assert len(candidates)==1,('query resolution',list(map(str,candidates)))
query=candidates[0]
ans={'case_id':3882,'historical_pr':14121,'repo':repository,'rule_id':rule,'file':path,'base_sha':base,'head_sha':head,'query':str(query),'toolchain':str(codeql),'results':{},'scope':'single production file preflight; confirm full-repository later'}
def fetch(sha):
 url='https://raw.githubusercontent.com/'+repository+'/'+sha+'/'+path
 req=urllib.request.Request(url,headers={'User-Agent':'Wits-case3882-prescan'})
 last=None
 for i in range(3):
  try:
   with urllib.request.urlopen(req,timeout=90) as handle:data=handle.read(2500001)
   assert len(data)<=2500000
   return data
  except Exception as e: last=e;time.sleep(3)
 raise RuntimeError('fetch failed '+str(last))
for arm,sha in [('before',base),('historical_pr',head)]:
 src=scratch/arm; f=src/path;f.parent.mkdir(parents=True)
 data=fetch(sha);f.write_bytes(data)
 ans['results'][arm]={'sha256':hashlib.sha256(data).hexdigest(),'file_bytes':len(data)}
 for label,command,timeout in [
  ('create',[codeql,'database','create',scratch/('db_'+arm),'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=15000'],1000),
  ('analyze',[codeql,'database','analyze',scratch/('db_'+arm),query,'--format=sarif-latest','--output='+str(out/(arm+'.sarif')),'--threads=4','--ram=15000'],1000)
 ]:
  p=subprocess.run(list(map(str,command)),cwd=src,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=timeout)
  (out/(arm+'_'+label+'.log')).write_text(p.stdout)
  ans['results'][arm][label+'_exit']=p.returncode
  print('RUN',arm,label,p.returncode,flush=True)
  if p.returncode:raise RuntimeError(arm+' '+label+' failed '+p.stdout[-500:])
 obj=json.loads((out/(arm+'.sarif')).read_text())
 hits=[]
 for run in obj.get('runs',[]):
  for entry in run.get('results',[]):
   if entry.get('ruleId')!=rule:continue
   loc=[]
   for l in entry.get('locations',[]):
    p=l.get('physicalLocation',{})
    loc.append({'file':p.get('artifactLocation',{}).get('uri'), 'line':p.get('region',{}).get('startLine')})
   hits.append({'locations':loc,'fingerprints':entry.get('partialFingerprints',{})})
 ans['results'][arm]['target_alert_count']=len(hits)
 ans['results'][arm]['target_alerts']=hits
(out/'RESULT.json').write_text(json.dumps(ans,indent=2)+'\n')
print('PRESCAN_COMPLETE',json.dumps({a:ans['results'][a]['target_alert_count'] for a in ('before','historical_pr')}),flush=True)
PY
