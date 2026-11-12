#!/bin/bash
#SBATCH --job-name=p2o2eval313
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2_o2eval_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2_o2eval_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import base64,gzip,hashlib,json,os,pathlib,re,subprocess,tarfile,tempfile,time,urllib.request,shutil
from pathlib import Path
home=Path.home()
root=home/'research_artifacts/prevention_pilot_phase2'
jid=os.environ['SLURM_JOB_ID']
out=root/('pilot16_O2_eval_job'+jid)
out.mkdir(exist_ok=False)
logs=out/'logs';logs.mkdir()
base_sha='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
patch_sha='31cff22de441d70338e7b3a3100db4718ce9a32546435589f3c95cfea5d86c1f'
archive_sha='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
query=home/'.codeql/packages/codeql/javascript-queries/2.3.11/Performance/PolynomialReDoS.ql'
codeql=home/'tools/codeql/codeql'
target='packages/pi-ai/src/utils/repair-tool-json.ts'
r={'case_id':313,'replicate':'O2','condition':'original_issue','baseline':base_sha,'patch_sha256':patch_sha,'source_issue_time_fidelity':'UNVERIFIED','status':'STARTED','tests':[]}
def write(): (out/'RESULT.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
def hsh(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def cmd(name,args,cwd,timeout=1200,required=False):
 log=logs/(name+'.log')
 print('START',name,flush=True)
 item={'name':name,'command':list(map(str,args)),'log':str(log.relative_to(out))}
 try:
  with log.open('x') as fh:
   p=subprocess.run(list(map(str,args)),cwd=cwd,stdout=fh,stderr=subprocess.STDOUT,timeout=timeout)
  item['exit_code']=p.returncode
 except subprocess.TimeoutExpired:item['exit_code']=None;item['error']='TIMEOUT'
 except Exception as e:item['exit_code']=None;item['error']=repr(e)[:400]
 r['tests'].append(item);write()
 print('END',name,item.get('exit_code'),flush=True)
 if required and item['exit_code']!=0:raise RuntimeError(name+' failed')
 return item['exit_code']==0
write()
b64='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'
patch=gzip.decompress(base64.b64decode(b64))
assert hashlib.sha256(patch).hexdigest()==patch_sha
patchfile=out/'PILOT_16_O2.patch';patchfile.write_bytes(patch)
expected={'src/resources/extensions/gsd/bootstrap/db-tools.ts','src/resources/extensions/gsd/prompts/complete-milestone.md','src/resources/extensions/gsd/templates/milestone-summary.md','src/resources/extensions/gsd/tests/complete-milestone.test.ts'}
pairs=re.findall(r'^diff --git a/(\S+) b/(\S+)$',patch.decode(),re.M)
assert len(pairs)==4 and {a for a,b in pairs}==expected and all(a==b for a,b in pairs)
r['changed_files']=sorted(expected)
scratch=Path(tempfile.mkdtemp(prefix='case313_O2_'+jid+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
src=scratch/'repo';src.mkdir()
tar=scratch/'base.tar.gz'
url='https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+base_sha
for attempt in range(3):
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Wits-Phase2-O2-Eval'})
  with urllib.request.urlopen(req,timeout=180) as response,tar.open('wb') as f:
   n=0
   while True:
    buf=response.read(1<<20)
    if not buf:break
    n+=len(buf);assert n<150_000_000;f.write(buf)
  break
 except Exception:
  if attempt==2:raise
  time.sleep(5)
r['base_archive_sha256']=hsh(tar)
assert r['base_archive_sha256']==archive_sha
with tarfile.open(tar,'r:gz') as archive:
 for m in archive:
  parts=pathlib.PurePosixPath(m.name).parts
  if len(parts)<2:continue
  rel=pathlib.PurePosixPath(*parts[1:])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe tar path')
  p=src.joinpath(*rel.parts)
  if m.isdir():p.mkdir(parents=True,exist_ok=True)
  elif m.isfile():
   p.parent.mkdir(parents=True,exist_ok=True)
   with archive.extractfile(m) as i,p.open('xb') as o:shutil.copyfileobj(i,o)
write()
cmd('patch_check',['git','apply','--check',patchfile],src,required=True)
cmd('patch_apply',['git','apply',patchfile],src,required=True)
r['patch_applies_to_frozen_base']=True
prompt=(src/'src/resources/extensions/gsd/prompts/complete-milestone.md').read_text()
ticks=chr(96)*3
m=re.findall(re.escape(ticks)+r'json\s*\n(.*?)\n\s*'+re.escape(ticks),prompt,re.S)
objects=[]
for text in m:
 try:objects.append(json.loads(text))
 except ValueError:pass
r['independent_prompt_schema_oracle']=any(all(isinstance(o.get(k),list) and all(isinstance(v,str) for v in o[k]) for k in ['keyDecisions','keyFiles','lessonsLearned']) for o in objects if isinstance(o,dict))
r['optional_fields_still_strings']=all((chr(96)+k+chr(96)+' (string)') in prompt for k in ['followUps','deviations'])
write()
assert codeql.is_file() and query.is_file()
r['codeql_query_sha256']=hsh(query)
r['codeql_binary_sha256']=hsh(codeql)
cmd('codeql_version',[codeql,'version'],src,90,True)
db=scratch/'database'
cmd('codeql_db',[codeql,'database','create',db,'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17500'],src,4000,True)
sarif=out/'target_rule.sarif'
cmd('codeql_rule',[codeql,'database','analyze',db,query,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=17500'],src,1800,True)
j=json.loads(sarif.read_text())
alerts=[]
for run in j.get('runs',[]):
 for a in run.get('results',[]):
  if a.get('ruleId')!='js/polynomial-redos':continue
  locations=[{'path':q.get('physicalLocation',{}).get('artifactLocation',{}).get('uri'),'line':q.get('physicalLocation',{}).get('region',{}).get('startLine')} for q in a.get('locations',[])]
  alerts.append({'locations':locations,'fingerprints':a.get('partialFingerprints',{})})
r['patched_rule_alerts_all_repo']=len(alerts)
r['patched_rule_alerts_target_file']=[a for a in alerts if any(target in str(q['path']) for q in a['locations'])]
r['new_target_alert_count']=len(r['patched_rule_alerts_target_file'])
r['repo_alert_count_change_vs_frozen_base']=len(alerts)-8
r['scanner_status']='COMPLETE'
write()
print('SCANNER',len(alerts),len(r['patched_rule_alerts_target_file']),flush=True)
node=shutil.which('node');npm=shutil.which('npm')
if node and npm:
 installed=cmd('npm_ci_ignore_scripts',[npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],src,1200)
 if installed:
  ok=cmd('focused_test',[node,'--import','./src/resources/extensions/gsd/tests/resolve-ts.mjs','--experimental-strip-types','--test','src/resources/extensions/gsd/tests/complete-milestone.test.ts'],src,600)
  r['focused_test_status']='PASS' if ok else 'FAIL'
 else:r['focused_test_status']='INSTALL_FAILED'
else:r['focused_test_status']='UNAVAILABLE_NODE'
r['functional_correctness']='NOT_ESTABLISHED__PROMPT_CONFORMANCE_ONLY'
r['status']='COMPLETE'
write()
print('RESULT',json.dumps({k:r[k] for k in ['patch_applies_to_frozen_base','independent_prompt_schema_oracle','optional_fields_still_strings','patched_rule_alerts_all_repo','new_target_alert_count','focused_test_status','functional_correctness']}),flush=True)
PY
