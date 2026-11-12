#!/usr/bin/env bash
#SBATCH --job-name=p3exactflow
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3exactflow_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3exactflow_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$PATH"
python3 - <<'PY'
import collections, hashlib, json, os, pathlib, subprocess, tarfile, urllib.request, sqlite3
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
out=root/('pilot3_exact_historical_flow_v3_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(parents=True,exist_ok=True)
assert not (out/'RESULT.json').exists(), 'Results already exist; refusing overwrite'
sha='070e05998c1e5e679094259d609f9f8e5c64995d'
prev='639150316e6f14cdc78e7dba8c6263504895b2e1'
target='3590371d06eebe91:1'
rule='js/insecure-temporary-file'
repo='Soul-Brews-Studio/arra-oracle-skills-cli'
scratch=pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('p3_hist_v3_'+os.environ['SLURM_JOB_ID'])
scratch.mkdir(parents=True,exist_ok=False)

def report(res):
 p=out/'RESULT.json';p.write_text(json.dumps(res,indent=2,ensure_ascii=False)+'\n')

def summarize_item(item):
 locs=item.get('locations',[])
 p=locs[0].get('physicalLocation',{}) if locs else {}
 f=p.get('artifactLocation',{}).get('uri')
 ln=p.get('region',{}).get('startLine')
 fps=item.get('partialFingerprints',{})
 flows=[]
 for codeflow in item.get('codeFlows',[]):
  for tf in codeflow.get('threadFlows',[]):
   steps=[]
   for x in tf.get('locations',[]):
    l=x.get('location',{})
    phys=l.get('physicalLocation',{})
    art=phys.get('artifactLocation',{})
    steps.append({'file':art.get('uri'),'line':phys.get('region',{}).get('startLine'),'description':l.get('message',{}).get('text')})
   if steps:
    flows.append({'origin':steps[0],'sink':steps[-1],'steps':len(steps),'through_changed_installer':any(s['file']=='src/cli/installer.ts' for s in steps),'path':steps})
 return {'sink_file':f,'sink_line':ln,'fp':fps,'codeflow_count':len(flows),'flows':flows}

def load_sarif(path):
 obj=json.loads(path.read_text())
 outarr=[]
 for run in obj.get('runs',[]):
  for v in run.get('results',[]):
   if v.get('ruleId')==rule:
    x=summarize_item(v)
    if x['sink_file']=='src/cli/skill-source.ts' and x['fp'].get('primaryLocationLineHash')==target:outarr.append(x)
 return {'matching_findings':len(outarr),'matches':outarr}

arms={
 'R1_baseline':'pilot3_scan_fix_job69698/rank_8',
 'R2_baseline':'pilot3_scan_r2_job69745/rank_8',
 'OW':'pilot3_arms_scan_OW_job69811/rank_8',
 'OP':'pilot3_arms_scan_OP_job69794/rank_8'
}
ans={'historical_pr':388,'pr_base_sha':prev,'pr_head_sha':sha,'target_rule':rule,'target_primary_fp':target,'arms':{}}
for name,dir in arms.items():
 x={}
 for state in ('base','patched'):
  p=root/dir/(state+'.sarif')
  if not p.exists():x[state]={'error':'MISSING_SARIF'}
  else:x[state]=load_sarif(p)
 ans['arms'][name]=x
 report(ans)
# historical scanner finding full original dataflow from frozen miner DB.
db=pathlib.Path.home()/'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db'
try:
 c=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True,timeout=15)
 row=c.execute("SELECT raw_json FROM scanner_findings WHERE id=1700 AND case_id=21942").fetchone()
 c.close()
 if row:
  h=summarize_item(json.loads(row[0]))
  ans['historical_record']=h
except Exception as e:
 ans['historical_record_error']=repr(e)
report(ans)
# Independent historical HEAD rule scan in isolated Slurm scratch.
p=scratch/'head.tar.gz'
url='https://codeload.github.com/'+repo+'/tar.gz/'+sha
req=urllib.request.Request(url,headers={'User-Agent':'Wits-case21942-causal-trace'})
try:
 with urllib.request.urlopen(req,timeout=120) as resp:
  blob=resp.read(80_000_001)
 assert len(blob)<80_000_001
 p.write_bytes(blob)
 source=scratch/'historical_head';source.mkdir()
 with tarfile.open(p,'r:gz') as tf:
  for m in tf:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   assert '..' not in rel.parts
   dest=source.joinpath(*rel.parts)
   if m.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tf.extractfile(m) as f, dest.open('xb') as g:
     import shutil
     shutil.copyfileobj(f,g)
 binary=pathlib.Path.home()/'tools/codeql/codeql'
 query=pathlib.Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11/Security/CWE-377/InsecureTemporaryFile.ql'
 assert binary.is_file() and query.is_file()
 commands=[
  ('head_create',[str(binary),'database','create',str(scratch/'codeql_head'),'--language=javascript-typescript','--source-root='+str(source),'--build-mode=none','--threads=4','--ram=15000']),
  ('head_analyze',[str(binary),'database','analyze',str(scratch/'codeql_head'),str(query),'--format=sarif-latest','--output='+str(out/'head.sarif'),'--threads=4','--ram=15000'])
 ]
 for name,cmd in commands:
  p=subprocess.run(cmd,cwd=source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8',errors='replace',timeout=1700)
  (out/(name+'.log')).write_text(p.stdout)
  ans[name+'_return_code']=p.returncode
  report(ans)
  if p.returncode:raise RuntimeError(name+' failed: '+p.stdout[-500:])
 ans['historical_head']=load_sarif(out/'head.sarif')
 report(ans)
except Exception as e:
 ans['historical_head_error']=repr(e)
 report(ans)
# Concise summary for prompt-sized review.
def info(name,state):
 z=ans.get('arms',{}).get(name,{}).get(state,{})
 matches=z.get('matches',[])
 return {'present':z.get('matching_findings'), 'flow_count':sum(m['codeflow_count'] for m in matches), 'origins':[f['origin'] for m in matches for f in m['flows']]}
simple={'historical_record':{'present':ans.get('historical_record',{}).get('sink_file'),'flow_count':ans.get('historical_record',{}).get('codeflow_count'),'origins':[f['origin'] for f in ans.get('historical_record',{}).get('flows',[])]},'historical_head':{'matching_findings':ans.get('historical_head',{}).get('matching_findings'),'flow_count':sum(m['codeflow_count'] for m in ans.get('historical_head',{}).get('matches',[]))},'arms':{a:{s:info(a,s) for s in ('base','patched')} for a in arms},'historical_head_error':ans.get('historical_head_error')}
(out/'SUMMARY.json').write_text(json.dumps(simple,indent=2)+'\n')
print(json.dumps(simple,indent=2),flush=True)
PY
