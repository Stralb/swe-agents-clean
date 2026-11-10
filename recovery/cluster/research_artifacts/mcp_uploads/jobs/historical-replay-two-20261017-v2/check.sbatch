#!/bin/bash
#SBATCH --job-name=p2hist2replay
#SBATCH --partition=bigbatch,batch
#SBATCH --array=0-1
#SBATCH --cpus-per-task=8
#SBATCH --mem=28G
#SBATCH --time=00:40:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path,PurePosixPath
from urllib.parse import quote
import json,os,hashlib,tarfile,zipfile,urllib.request,tempfile,re,collections,subprocess
CASES=[
 {'id':8147,'repo':'superagent-ai/grok-cli','head':'75e5c0a6e51621b954e053e87494af4ffc5b5b8d','before':70128,'rule':'js/file-system-race','historical_path':'src/utils/at-mentions.ts'},
 {'id':15686,'repo':'builderz-labs/mission-control','head':'9083790af570343991699792905edbb18c02356f','before':70129,'rule':'js/file-access-to-http','historical_path':'src/lib/github.ts'},
]
c=CASES[int(os.environ['SLURM_ARRAY_TASK_ID'])]
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
out=root/('screen5_hist_%d_job%s'%(c['id'],os.environ['SLURM_JOB_ID']))
out.mkdir(exist_ok=False)
data={'id':c['id'],'rule':c['rule'],'state':'STARTED','repo':c['repo'],'head_sha':c['head'],'query':'codeql/javascript-queries:codeql-suites/javascript-security-extended.qls'}
def save(): (out/'RESULT.json').write_text(json.dumps(data,indent=2)+'\n')
def run(label,cmd,cwd,timeout=2100):
 with (out/(label+'.log')).open('w') as o:
  p=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=o,stderr=subprocess.STDOUT,timeout=timeout)
 data[label+'_exit']=p.returncode;save();return p.returncode==0
def findings(path):
 sarif=json.loads(Path(path).read_text())
 hits=[]
 for runitem in sarif.get('runs',[]):
  for row in runitem.get('results',[]):
   if row.get('ruleId')!=c['rule']:continue
   loc=row.get('locations',[{}])[0].get('physicalLocation',{})
   hits.append({'uri':loc.get('artifactLocation',{}).get('uri'),'line':loc.get('region',{}).get('startLine'),'message':row.get('message',{}).get('text',''),'fingerprints':row.get('partialFingerprints',{})})
 return hits
try:
 original=root/('screen5_eval_%d_job%d'%(c['id'],c['before']))/'base.sarif'
 assert original.is_file()
 data['base_count']=len(findings(original))
 temp=Path(tempfile.mkdtemp(prefix='historical_%d_'%c['id'],dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 archive=temp/'head.tar.gz'
 url='https://codeload.github.com/'+quote(c['repo'],safe='/')+'/tar.gz/'+c['head']
 req=urllib.request.Request(url,headers={'User-Agent':'WitsResearch-CodeQL-HistoricalControl'})
 with urllib.request.urlopen(req,timeout=160) as response,archive.open('wb') as f:
  size=0
  while True:
   buf=response.read(1048576)
   if not buf:break
   size+=len(buf)
   if size>130*1024*1024:raise ValueError('Head archive too large')
   f.write(buf)
 data['head_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
 head=temp/'HEAD';head.mkdir()
 with tarfile.open(archive,'r:gz') as t:
  for m in t:
   seg=PurePosixPath(m.name).parts
   if len(seg)<2 or not m.isfile():continue
   rel=PurePosixPath(*seg[1:])
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('Bad archive path')
   path=head/str(rel);path.parent.mkdir(parents=True,exist_ok=True)
   with t.extractfile(m) as fi:path.write_bytes(fi.read())
 db=out/'db_head'
 bin=Path.home()/'tools/codeql/codeql'
 if not run('create_head',[bin,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(head),'--threads=8','--ram=27000'],head,2100):raise RuntimeError('CodeQL head DB create failed')
 if not run('scan_head',[bin,'database','analyze',db,data['query'],'--format=sarif-latest','--output',out/'head.sarif','--threads=8','--ram=27000'],head,2100):raise RuntimeError('CodeQL historical scan failed')
 baseline=findings(original);historical=findings(out/'head.sarif')
 keys=lambda x:(x['uri'],x['fingerprints'].get('primaryLocationLineHash') or x['message'],x['fingerprints'].get('primaryLocationStartColumnFingerprint') or '')
 counts=collections.Counter(map(keys,baseline))
 fresh=[]
 for f in historical:
  k=keys(f)
  if counts[k]>0:counts[k]-=1
  else:fresh.append(f)
 data.update({'state':'COMPLETE','historical_head_count':len(historical),'historical_new_count':len(fresh),'historical_new_findings':fresh,'historical_new_target_path':[x for x in fresh if x['uri']==c['historical_path']]})
except BaseException as e:
 data['state']='ERROR';data['error']=repr(e)[:1000]
save()
print(json.dumps({k:data.get(k) for k in ['id','state','base_count','historical_head_count','historical_new_count','historical_new_target_path','error']}),flush=True)
PY
