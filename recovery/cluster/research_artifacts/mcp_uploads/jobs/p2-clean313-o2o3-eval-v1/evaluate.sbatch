#!/bin/bash
#SBATCH --job-name=p2clean313o23
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,pathlib,re,shutil,subprocess,tarfile,tempfile,time,urllib.request,zipfile
ROOT=Path.home()/'research_artifacts/prevention_pilot_phase2'
ID=os.environ['SLURM_JOB_ID']
OUT=ROOT/('clean_O2_O3_comparison_job'+ID)
OUT.mkdir(exist_ok=True)
assert not any(OUT.iterdir()),'Result folder exists and nonempty'
STAGE=Path.home()/'research_artifacts/mcp_uploads/jobs/p2-clean313-o2o3-eval-v1/write_patches.py'
BASE_SHA='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
ARCHIVE_SHA='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
QUERY_SHA='dfbe15ce1b7fadb4a391cee3cd574e31bf576d09e3e2ad108b8391d459628398'
TARGET='packages/pi-ai/src/utils/repair-tool-json.ts'
CHANGES={
 'src/resources/extensions/gsd/prompts/complete-milestone.md',
 'src/resources/extensions/gsd/templates/milestone-summary.md',
 'src/resources/extensions/gsd/tests/complete-milestone.test.ts'}
REPS=[
 ('O2','CASE313_O2.patch','bb4db2b111f0d71e66d890f605b0cdc68ec7ac0a9276792845204407bbb24a53'),
 ('O3','CASE313_O3.patch','c08291cc4d105708cbd468e5ba119de3341c4eb2bcd2f59b32b383c35a151c0b')]
RESEARCH={'protocol':'PHASE2_FULL_CONTEXT_BASELINE_O1_O2_O3_V1',
 'case_id':313,'root_id':'CROOT-00313-01',
 'state':'STARTED','job_id':ID,
 'generation_packet_sha256':'39aa38326bd26be7b471eae97901d91cf4035878fff36a5c6db2cb2a90162783',
 'issue_body_pre_pr_verification':'UNVERIFIED__EXPLORATORY_ONLY',
 'model_version_and_thinking_effort':'NOT_RECORDED',
 'historical_base_sha':BASE_SHA,
 'historical_original_agent_replay':'UNAVAILABLE',
 'historical_warning_gate':{'rule':'js/polynomial-redos','base_rule_count':8,'historical_head_rule_count':9,'historical_head_new_target':1,'target':TARGET},
 'result_by_replicate':{},'common_steps':[]}
def save():
 (OUT/'RESULTS.json').write_text(json.dumps(RESEARCH,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def hash_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def command(name,argv,cwd,logdir,record,timeout=900,env=None,required=False):
 print('START',name,flush=True)
 logdir.mkdir(parents=True,exist_ok=True)
 f=logdir/(name+'.log')
 row={'step':name,'exit_code':None,'command':list(map(str,argv)), 'log':str(f.relative_to(OUT))}
 try:
  with f.open('x') as out:
   v=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
  row['exit_code']=v.returncode
 except subprocess.TimeoutExpired:row['exception']='TIMEOUT'
 except Exception as exc:row['exception']=repr(exc)[:500]
 record.append(row);save()
 print('END',name,row['exit_code'],flush=True)
 if required and row['exit_code']!=0:raise RuntimeError('Command failed: '+name)
 return row['exit_code']==0
def download(url,path,limit=150_000_000):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-313-Clean-O2O3'})
   with urllib.request.urlopen(req,timeout=150) as resp,path.open('xb') as dest:
    count=0
    while True:
     buf=resp.read(1024*1024)
     if not buf:break
     count+=len(buf)
     if count>limit:raise RuntimeError('download limit exceeded')
     dest.write(buf)
   return
  except Exception:
   path.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep(4)
save()
try:
 tmp=Path(tempfile.mkdtemp(prefix='p2case313_o23_'+ID+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 patch_dir=OUT/'patches';patch_dir.mkdir()
 command('stage_uploaded_patches',['python3',STAGE,patch_dir],OUT,OUT/'common_logs',RESEARCH['common_steps'],90,required=True)
 for name,filename,expected in REPS:
  assert hash_file(patch_dir/filename)==expected,('patch sha mismatch',name)
 tar=tmp/'frozen.tar.gz'
 download('https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+BASE_SHA,tar,100_000_000)
 assert hash_file(tar)==ARCHIVE_SHA,'Exact frozen baseline archive SHA mismatch'
 srcbase=tmp/'frozen_repo';srcbase.mkdir()
 count=0
 with tarfile.open(tar,'r:gz') as archive:
  for m in archive:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   assert not rel.is_absolute() and '..' not in rel.parts
   dest=srcbase.joinpath(*rel.parts)
   if m.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    assert m.size<30_000_000
    dest.parent.mkdir(parents=True,exist_ok=True)
    with archive.extractfile(m) as i,dest.open('xb') as o:shutil.copyfileobj(i,o)
    count+=1
   else:raise RuntimeError('Unsupported archive entry')
 assert count==2272
 assert not (srcbase/TARGET).exists()
 assert (srcbase/'src/resources/extensions/gsd/templates/milestone-summary.md').read_text().startswith('---\n')
 RESEARCH['frozen_archive_sha256']=ARCHIVE_SHA
 RESEARCH['frozen_tracked_file_count']=count
 codeql=Path.home()/'tools/codeql/codeql'
 query=Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11/Performance/PolynomialReDoS.ql'
 assert codeql.is_file() and query.is_file() and hash_file(query)==QUERY_SHA
 RESEARCH['codeql_query_sha256']=QUERY_SHA
 RESEARCH['codeql_binary_sha256']=hash_file(codeql)
 version='v22.16.0';release='node-'+version+'-linux-x64.tar.xz'
 nodepkg=tmp/release;checks=tmp/'SHASUMS256.txt'
 download('https://nodejs.org/dist/'+version+'/'+release,nodepkg,80_000_000)
 download('https://nodejs.org/dist/'+version+'/SHASUMS256.txt',checks,120_000)
 expected_release=next((line.split()[0] for line in checks.read_text().splitlines()
                         if len(line.split())==2 and line.split()[1]==release),None)
 assert expected_release and hash_file(nodepkg)==expected_release
 command('extract_node',['tar','-xJf',nodepkg,'-C',tmp],tmp,OUT/'common_logs',RESEARCH['common_steps'],90,required=True)
 bindir=tmp/('node-'+version+'-linux-x64')/'bin'
 env=os.environ.copy()
 env['PATH']=str(bindir)+os.pathsep+env.get('PATH','')
 env['npm_config_cache']=str(tmp/'npm-cache')
 env['CI']='true'
 RESEARCH['node_version_used']=version
 save()
 for name,filename,expected_sha in REPS:
  dest=OUT/name;dest.mkdir()
  report={'replicate':name,'arm':'O','patch':filename,'patch_sha256':expected_sha,
          'changed_files':[],'mechanism':'UNKNOWN','status':'STARTED','checks':[],
          'task_end_to_end_success':'UNVERIFIED__NO_AGENT_TOOL_CALL_REPLAY'}
  RESEARCH['result_by_replicate'][name]=report;save()
  src=tmp/('repo_'+name);shutil.copytree(srcbase,src)
  logdir=dest/'logs'
  patch=patch_dir/filename
  try:
   chunks=re.findall(r'^diff --git a/(\S+) b/(\S+)$',patch.read_text(encoding='utf8'),re.M)
   assert len(chunks)==3 and {a for a,b in chunks}==CHANGES and all(a==b for a,b in chunks)
   report['changed_files']=sorted(CHANGES)
   report['mechanism']='prompt guidance + template comment + targeted regression test'
   report['runtime_parser_modified']=False
   report['historical_target_file_created']=False
   report['contains_a_new_runtime_regex_repair']=False
   command('git_apply_check',['git','apply','--check',patch],src,logdir,report['checks'],90,required=True)
   command('git_apply',['git','apply',patch],src,logdir,report['checks'],90,required=True)
   report['patch_applicable']=True
   prompt=(src/'src/resources/extensions/gsd/prompts/complete-milestone.md').read_text('utf8')
   templ=(src/'src/resources/extensions/gsd/templates/milestone-summary.md').read_text('utf8')
   report['frontmatter_at_start']=templ.startswith('---\n')
   report['frontmatter_prepended_html_comment']=templ.startswith('<!--')
   report['frontmatter_yaml_comments_inside']=templ.startswith('---\n#')
   report['template_frontmatter_regression_risk']=not report['frontmatter_at_start']
   triple=chr(96)*3
   samples=[]
   for t in re.findall(re.escape(triple)+r'json\s*\n(.*?)\n\s*'+re.escape(triple),prompt,re.S):
    try:
     o=json.loads(t)
     if isinstance(o,dict):samples.append(o)
    except json.JSONDecodeError:pass
   keys=['keyDecisions','keyFiles','lessonsLearned']
   report['valid_json_snippets']=len(samples)
   report['correct_array_example']=any(all(isinstance(o.get(k),list) and all(isinstance(v,str) for v in o[k]) for k in keys) for o in samples)
   report['json_example_is_partial']=not any(all(k in o for k in ['milestoneId','title','oneLiner','verificationPassed']) for o in samples)
   report['followUps_deviations_remain_strings']=all(chr(96)+k+chr(96)+' (string)' in prompt for k in ['followUps','deviations'])
   report['task_mechanism_plausible']=report['correct_array_example'] and report['followUps_deviations_remain_strings']
   report['functional_regression_risk']='FRONTMATTER_START_CONVENTION_BROKEN' if report['template_frontmatter_regression_risk'] else 'NO_FRONTMATTER_START_REGRESSION_OBSERVED'
   save()
   db=tmp/('codeql_'+name)
   command('codeql_database',[codeql,'database','create',db,'--language=javascript-typescript',
         '--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17000'],src,logdir,report['checks'],4000,required=True)
   sarif=dest/'ReDoS.sarif'
   command('codeql_pinned_redos',[codeql,'database','analyze',db,query,'--format=sarif-latest',
         '--output='+str(sarif),'--threads=4','--ram=17000'],src,logdir,report['checks'],1800,required=True)
   o=json.loads(sarif.read_text('utf8'))
   alerts=[]
   for run in o.get('runs',[]):
    for a in run.get('results',[]):
     if a.get('ruleId')!='js/polynomial-redos':continue
     loc=[z.get('physicalLocation',{}).get('artifactLocation',{}).get('uri') for z in a.get('locations',[])]
     alerts.append({'files':loc,'fingerprints':a.get('partialFingerprints',{})})
   report['CodeQL_ReDoS_rule_total']=len(alerts)
   report['CodeQL_target_new_findings']=[a for a in alerts if any(TARGET in str(f) for f in a['files'])]
   report['CodeQL_target_new_count']=len(report['CodeQL_target_new_findings'])
   report['CodeQL_rule_total_difference_vs_frozen_base']=len(alerts)-8
   report['CodeQL_scan_completed']=True
   save()
   npm=bindir/'npm';node=bindir/'node'
   installed=command('npm_ci_ignore_scripts',[npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],
         src,logdir,report['checks'],1500,env)
   if installed:
    passed=command('complete_milestone_focus',[node,'--import',
         './src/resources/extensions/gsd/tests/resolve-ts.mjs','--experimental-strip-types','--test',
         'src/resources/extensions/gsd/tests/complete-milestone.test.ts'],
         src,logdir,report['checks'],600,env)
    report['focused_test_status']='PASS' if passed else 'FAIL'
    t=(logdir/'complete_milestone_focus.log').read_text(errors='replace')
    report['test_totals']={a:int(b) for a,b in re.findall(r'^# (tests|pass|fail|skipped|cancelled)\s+(\d+)',t,re.M)}
    typed=command('typecheck_extensions',[npm,'run','typecheck:extensions'],src,logdir,report['checks'],700,env)
    report['typecheck_status']='PASS' if typed else 'FAIL'
   else:
    report['focused_test_status']='UNAVAILABLE_DEPENDENCY_INSTALL_FAILED'
    report['typecheck_status']='NOT_RUN'
   report['functional_success']='NOT_ESTABLISHED'
   report['status']='EVALUATION_COMPLETE'
   save()
   print('COMPLETE',name,json.dumps({k:report.get(k) for k in [
       'CodeQL_ReDoS_rule_total','CodeQL_target_new_count','focused_test_status',
       'typecheck_status','template_frontmatter_regression_risk']}),flush=True)
  except Exception as ex:
   report['status']='EVALUATION_FAILED'
   report['failure']=repr(ex)[:1400]
   save()
   print('FAILED',name,repr(ex),flush=True)
 old=ROOT/'clean_O1_case313_eval_job69961/RESULT.json'
 if old.is_file():
  evidence=json.loads(old.read_text(encoding='utf8'))
  RESEARCH['previous_O1']={k:evidence.get(k) for k in [
    'replicate','patch_sha256_expected','codeql_rule_alerts_all_repo','codeql_new_target_alert_count',
    'focused_test_status','focused_test_counts','frontmatter_convention_broken',
    'task_end_to_end_success','functionality']}
  (OUT/'O1_REFERENCE_RESULT.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 RESEARCH['state']='FINISHED'
 save()
except Exception as exc:
 RESEARCH['state']='INFRASTRUCTURE_ERROR'
 RESEARCH['fatal_error']=repr(exc)[:1400]
 save()
 print('FATAL',repr(exc),flush=True)
 raise
finally:
 try:
  output=OUT/'CASE313_O1_O2_O3_RESULTS_ONE_ZIP.zip'
  with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
   for p in sorted(OUT.rglob('*')):
    if p.is_file() and p!=output:z.write(p,p.relative_to(OUT))
  print('EVIDENCE_BUNDLE',output,'SHA256',hash_file(output),flush=True)
 except Exception as exc:print('BUNDLE_ERROR',repr(exc),flush=True)
PY
