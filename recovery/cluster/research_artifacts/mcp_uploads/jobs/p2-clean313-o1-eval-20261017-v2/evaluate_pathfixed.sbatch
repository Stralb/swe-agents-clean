#!/bin/bash
#SBATCH --job-name=p2clean313o
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import hashlib,json,os,pathlib,re,shutil,subprocess,tarfile,tempfile,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path.home()/'research_artifacts/prevention_pilot_phase2'
J=os.environ['SLURM_JOB_ID']
OUT=ROOT/('clean_O1_case313_eval_job'+J)
OUT.mkdir(exist_ok=True)
assert not any(OUT.iterdir()),'Refuse to overwrite an existing result folder'
LOG=OUT/'logs';LOG.mkdir()
BASE='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
PATCH_SHA='517bccfc788318cf69848d6ed4396ddd7beb325dd542b023ec56ba50ca4c716b'
ARCHIVE_SHA='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
QUERY_SHA='dfbe15ce1b7fadb4a391cee3cd574e31bf576d09e3e2ad108b8391d459628398'
TARGET='packages/pi-ai/src/utils/repair-tool-json.ts'
EXPECTED_CHANGED={
 'src/resources/extensions/gsd/prompts/complete-milestone.md',
 'src/resources/extensions/gsd/templates/milestone-summary.md'}
R={
 'protocol':'PHASE2_CASE313_FULL_UNCURATED_O_BASELINE_EVAL_V1',
 'case_id':313,'root_id':'CROOT-00313-01','arm':'O','replicate':'clean_O1',
 'previous_curated_replicates_pooled':False,
 'generation_input':'neutral_full_context_job69947 / full 2272-file source packet',
 'generation_packet_sha256':'39aa38326bd26be7b471eae97901d91cf4035878fff36a5c6db2cb2a90162783',
 'issue_body_temporal_verdict':'POST_PR_EDIT_POSSIBLE__EXPLORATORY_ONLY',
 'model_version':'NOT_CAPTURED',
 'historical_base_sha':BASE,'historical_base_rule_alerts':8,'historical_base_target_alerts':0,
 'historical_head_rule_alerts':9,'historical_head_target_alerts':1,
 'rule_id':'js/polynomial-redos','rule_query_sha256':QUERY_SHA,'target_file':TARGET,
 'patch_sha256_expected':PATCH_SHA,'state':'STARTED','steps':[],
 'task_end_to_end_success':'UNVERIFIED',
 'functionality':'INCONCLUSIVE'}
def save():
 (OUT/'RESULT.json').write_text(json.dumps(R,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def digest(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def download(url,path,cap=100_000_000):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Phase2-Clean313O-Evaluation'})
   with urllib.request.urlopen(req,timeout=150) as inp,path.open('xb') as f:
    n=0
    while True:
     block=inp.read(1024*1024)
     if not block:break
     n+=len(block)
     if n>cap:raise RuntimeError('download exceeded limit')
     f.write(block)
   return
  except Exception:
   path.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep(4)
def step(name,cmd,cwd,timeout=900,env=None,required=False):
 print('START',name,flush=True)
 logfile=LOG/(name+'.log')
 row={'step':name,'command':list(map(str,cmd)),'log':'logs/'+name+'.log'}
 try:
  with logfile.open('x') as fh:
   q=subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=fh,stderr=subprocess.STDOUT,timeout=timeout)
  row['exit_code']=q.returncode
 except subprocess.TimeoutExpired:row.update(exit_code=None,reason='TIMEOUT')
 except Exception as e:row.update(exit_code=None,reason=repr(e)[:500])
 R['steps'].append(row);save()
 print('END',name,row.get('exit_code'),flush=True)
 if required and row.get('exit_code')!=0:raise RuntimeError('Required step failed: '+name)
 return row.get('exit_code')==0
save()
try:
 staged=Path.home()/'research_artifacts/mcp_uploads/jobs/p2-clean313-o1-eval-20261017-v2/write_patch.py'
 assert staged.is_file(),'Missing patch staging script'
 patchfile=OUT/'issue-2660.patch'
 step('materialize_user_patch',['python3',staged,patchfile],OUT,60,required=True)
 assert sha_file(patchfile)==PATCH_SHA,'Patch differs from user-uploaded bytes'
 patch=patchfile.read_text('utf8')
 changed=re.findall(r'^diff --git a/(\S+) b/(\S+)$',patch,re.M)
 assert len(changed)==2 and {a for a,b in changed}==EXPECTED_CHANGED and all(a==b for a,b in changed)
 R['changed_files']=sorted(EXPECTED_CHANGED)
 R['strategy']='prompt-schema + template-comment'
 R['touches_historical_target_file']=TARGET in EXPECTED_CHANGED
 save()
 tmp=Path(tempfile.mkdtemp(prefix='p2clean313o_'+J+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 archive=tmp/'base.tar.gz'
 download('https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+BASE,archive)
 R['base_archive_sha256']=sha_file(archive)
 assert R['base_archive_sha256']==ARCHIVE_SHA,'Frozen source checksum mismatch'
 src=tmp/'repo';src.mkdir()
 files=0
 with tarfile.open(archive,'r:gz') as tar:
  for m in tar:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe archive path')
   dst=src.joinpath(*rel.parts)
   if m.isdir():dst.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    if m.size>=30_000_000:raise RuntimeError('Source file oversize')
    files+=1;dst.parent.mkdir(parents=True,exist_ok=True)
    with tar.extractfile(m) as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
   else:raise RuntimeError('Unexpected symlink or other archive member')
 assert files==2272,('Wrong frozen file count',files)
 R['frozen_base_file_count']=files
 tp=src/'src/resources/extensions/gsd/templates/milestone-summary.md'
 pp=src/'src/resources/extensions/gsd/prompts/complete-milestone.md'
 before=tp.read_text(encoding='utf8')
 assert before.startswith('---\n')
 assert not (src/TARGET).exists()
 save()
 step('git_apply_check',['git','apply','--check',patchfile],src,90,required=True)
 step('git_apply',['git','apply',patchfile],src,90,required=True)
 R['patch_applies_to_frozen_base']=True
 prompt=pp.read_text(encoding='utf8')
 template=tp.read_text(encoding='utf8')
 R['template_frontmatter_starts_at_line_1_before_patch']=True
 R['template_frontmatter_starts_at_line_1_after_patch']=template.startswith('---\n')
 R['template_comment_prepended_before_yaml']=template.startswith('<!--')
 R['frontmatter_convention_broken']=not R['template_frontmatter_starts_at_line_1_after_patch']
 # Verify actual embedded sample parses and has required array/string/boolean values.
 ticks=chr(96)*3
 examples=[]
 for block in re.findall(re.escape(ticks)+r'json\s*\n(.*?)\n\s*'+re.escape(ticks),prompt,re.S):
  try:
   j=json.loads(block)
   if isinstance(j,dict):examples.append(j)
  except json.JSONDecodeError:pass
 R['valid_json_object_examples']=len(examples)
 R['prompt_has_typed_json_example']=any(
   all(isinstance(j.get(k),list) and all(isinstance(x,str) for x in j[k])
       for k in ('keyDecisions','keyFiles','lessonsLearned'))
   and j.get('verificationPassed') is True and isinstance(j.get('oneLiner'),str)
   for j in examples)
 R['optional_string_parameter_docs_preserved']=all(
   chr(96)+k+chr(96)+' (string)' in prompt for k in ('followUps','deviations'))
 R['task_design_mechanism_plausible']='YES' if R['prompt_has_typed_json_example'] else 'NO'
 save()
 codeql=Path.home()/'tools/codeql/codeql'
 query=Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11/Performance/PolynomialReDoS.ql'
 assert codeql.is_file() and query.is_file()
 assert sha_file(query)==QUERY_SHA,'CodeQL query mismatch'
 R['codeql_binary_sha256']=sha_file(codeql)
 step('codeql_version',[codeql,'version'],src,60,required=True)
 db=tmp/'codeql_db'
 step('codeql_create',[codeql,'database','create',db,'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17500'],src,3000,required=True)
 sarif=OUT/'target_rule.sarif'
 step('codeql_target',[codeql,'database','analyze',db,query,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=17500'],src,1800,required=True)
 data=json.loads(sarif.read_text(encoding='utf8'))
 hits=[]
 for run in data.get('runs',[]):
  for hit in run.get('results',[]):
   if hit.get('ruleId')!='js/polynomial-redos':continue
   locations=[{'path':z.get('physicalLocation',{}).get('artifactLocation',{}).get('uri'),
               'line':z.get('physicalLocation',{}).get('region',{}).get('startLine')}
              for z in hit.get('locations',[])]
   hits.append({'locations':locations,'fingerprints':hit.get('partialFingerprints',{})})
 R['codeql_rule_alerts_all_repo']=len(hits)
 R['codeql_target_alerts']=[h for h in hits if any(TARGET in str(x['path']) for x in h['locations'])]
 R['codeql_new_target_alert_count']=len(R['codeql_target_alerts'])
 R['codeql_all_repo_change_vs_frozen_base']=len(hits)-8
 R['codeql_status']='PASS';save()
 print('CODEQL',len(hits),'TARGET',R['codeql_new_target_alert_count'],flush=True)
 # Node 22, official checksum verified, isolated in batch scratch.
 version='v22.16.0'; name='node-'+version+'-linux-x64.tar.xz'
 node_tar=tmp/name;checks=tmp/'SHASUMS256.txt'
 download('https://nodejs.org/dist/'+version+'/'+name,node_tar,80_000_000)
 download('https://nodejs.org/dist/'+version+'/SHASUMS256.txt',checks,120_000)
 expected=next((line.split()[0] for line in checks.read_text().splitlines()
                if len(line.split())==2 and line.split()[1]==name),None)
 assert expected and sha_file(node_tar)==expected,'Node package checksum mismatch'
 step('node_extract',['tar','-xJf',node_tar,'-C',tmp],tmp,90,required=True)
 b=tmp/('node-'+version+'-linux-x64')/'bin'
 node=b/'node';npm=b/'npm'
 env=os.environ.copy();env['PATH']=str(b)+os.pathsep+env.get('PATH','')
 env['CI']='true';env['npm_config_cache']=str(tmp/'npm-cache')
 step('node_version',[node,'--version'],src,30,env,required=True)
 installed=step('npm_ci_ignore_scripts',[npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],src,1200,env)
 if installed:
  passed=step('complete_milestone_focused_tests',
    [node,'--import','./src/resources/extensions/gsd/tests/resolve-ts.mjs',
     '--experimental-strip-types','--test','src/resources/extensions/gsd/tests/complete-milestone.test.ts'],
    src,600,env)
  R['focused_test_status']='PASS' if passed else 'FAIL'
  content=(LOG/'complete_milestone_focused_tests.log').read_text(errors='replace')
  R['focused_test_counts']={k:int(v) for k,v in re.findall(r'^# (tests|pass|fail|skipped)\s+(\d+)',content,re.M)}
 else:R['focused_test_status']='NOT_RUN__DEPENDENCY_INSTALL_FAILED'
 R['task_end_to_end_success']='UNVERIFIED__NO_LLM_TOOL_CALL_REPLAY'
 R['functionality']='INCONCLUSIVE__PROMPT_MECHANISM_PLAUSIBLE_BUT_FRONTMATTER_REGRESSION'
 R['state']='EVALUATION_COMPLETE';save()
 print('SUMMARY',json.dumps({k:R[k] for k in ('patch_applies_to_frozen_base','prompt_has_typed_json_example',
     'frontmatter_convention_broken','codeql_rule_alerts_all_repo','codeql_new_target_alert_count',
     'focused_test_status','task_end_to_end_success')}),flush=True)
except Exception as exc:
 R['state']='EVALUATION_FAILED';R['error']=repr(exc)[:1000];save()
 print('EVALUATION_ERROR',repr(exc),flush=True)
 raise
finally:
 try:
  single=OUT/'CASE313_CLEAN_O1_EVIDENCE.zip'
  with zipfile.ZipFile(single,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
   for f in sorted(OUT.rglob('*')):
    if f.is_file() and f!=single:
     z.write(f,f.relative_to(OUT))
  print('ONE_ZIP',single,'SHA256',sha_file(single),flush=True)
 except Exception as e:print('PACKAGING_FAILURE',repr(e),flush=True)
PY
