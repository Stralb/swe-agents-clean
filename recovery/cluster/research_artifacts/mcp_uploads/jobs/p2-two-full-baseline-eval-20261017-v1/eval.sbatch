#!/bin/bash
#SBATCH --job-name=p2eval2cases
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,pathlib,re,shutil,subprocess,tarfile,tempfile,time,urllib.request,zipfile
ROOT=Path.home()/'research_artifacts/prevention_pilot_phase2'
OUT=ROOT/('two_new_clean_baselines_eval_job'+os.environ['SLURM_JOB_ID'])
OUT.mkdir(exist_ok=True);assert not any(OUT.iterdir())
STAGE=Path.home()/'research_artifacts/mcp_uploads/jobs/p2-two-full-baseline-eval-20261017-v1'
CASES=[
 {'id':21942,'repo':'Soul-Brews-Studio/arra-oracle-skills-cli','base':'639150316e6f14cdc78e7dba8c6263504895b2e1','head':'070e05998c1e5e679094259d609f9f8e5c64995d','archive_sha':'e9ad762c91e49756f0ace64ccb3678af8711d2c304b5d110f2871f994bad6aec','patch':'codex-0130-fix.patch','sha':'77793cece5bc6ad956ed347e54e07d206e9bf5e4acc284b642b4c7b520b4ec74','id_rule':'js/insecure-temporary-file','query':'InsecureTemporaryFile.ql','chunks':['case8_p0.py']},
 {'id':16392,'repo':'xiaotianfotos/homerail','base':'e3d9382886a07dce4df7ff4aaedffd9613a09a4d','head':'a835368b1e0dccbbdaf8dcff2dd17f9bc221fa03','archive_sha':'4c214d2e3435b6364e0b4df893b0f9653ff14fa797b29d71ad85983ff042bc35','patch':'qwen-structured-handoff.patch','sha':'a2f39a285ead81d85dd7740b2c71f833c93384af03b118423fdda6e07a9be936','id_rule':'js/insecure-randomness','query':'InsecureRandomness.ql','chunks':['case4_p0.py','case4_p1.py']}
]
S={'protocol':'FULL_REPOSITORY_BASELINE_O1_TWO_CASES','state':'RUNNING','cases':{},'time_travel':'DB issue last updated before historical PR, exact historical text edits not independently archived','same_model_setting':'NOT_VERIFIED','interpretation':'Scanner-positive only when new and attributable; tests do not prove full task behavior'}
def save():(OUT/'RESULTS.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n')
def hashfile(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for data in iter(lambda:f.read(1<<20),b''):h.update(data)
 return h.hexdigest()
def cmd(name,argv,cwd,record,timeout=1200,env=None):
 lf=OUT/record['case']/'logs';lf.mkdir(exist_ok=True,parents=True)
 log=lf/(name+'.log')
 item={'step':name,'exit':None,'log':str(log.relative_to(OUT))}
 print('START',record['case'],name,flush=True)
 try:
  with log.open('x') as f:
   x=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  item['exit']=x.returncode
 except Exception as e:item['exception']=repr(e)[:300]
 record['steps'].append(item);save()
 print('END',record['case'],name,item['exit'],flush=True)
 return item['exit']==0
def dl(url,p):
 for i in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WitsResearchCleanBaseline20261017'}),timeout=150) as f,p.open('xb') as d:
    n=0
    while True:
     b=f.read(1<<20)
     if not b:break
     n+=len(b);assert n<100_000_000
     d.write(b)
   return
  except Exception:
   p.unlink(missing_ok=True)
   if i==2:raise
   time.sleep(4)
def untar(archive,root):
 root.mkdir()
 count=0
 with tarfile.open(archive,'r:gz') as t:
  for m in t:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   assert not rel.is_absolute() and '..' not in rel.parts and chr(92) not in str(rel)
   dest=root.joinpath(*rel.parts)
   if m.isdir():dest.mkdir(exist_ok=True,parents=True)
   elif m.isfile():
    assert m.size<35_000_000
    dest.parent.mkdir(exist_ok=True,parents=True)
    with t.extractfile(m) as f,dest.open('xb') as o:shutil.copyfileobj(f,o)
    count+=1
   elif m.issym():
    dest.parent.mkdir(exist_ok=True,parents=True)
    assert not pathlib.PurePosixPath(m.linkname).is_absolute()
    assert os.path.commonpath([str(root.resolve()),str((dest.parent/m.linkname).resolve())])==str(root.resolve())
    os.symlink(m.linkname,dest)
   else:raise RuntimeError('unexpected archive type')
 return count
def hits(path,rule):
 s=json.loads(path.read_text())
 result=[]
 for run in s.get('runs',[]):
  for x in run.get('results',[]):
   if x.get('ruleId')!=rule:continue
   first=(x.get('locations') or [{}])[0].get('physicalLocation') or {}
   fp=x.get('partialFingerprints') or {}
   result.append({'path':first.get('artifactLocation',{}).get('uri',''),'line':first.get('region',{}).get('startLine'),
                  'hash':fp.get('primaryLocationLineHash'), 'column':fp.get('primaryLocationStartColumnFingerprint')})
 return result
def new(old,later):
 keys={(x['path'],x['hash'],x['column']) for x in old}
 return [x for x in later if (x['path'],x['hash'],x['column']) not in keys]
def evaluate(label,src,task,query,sub):
 database=sub/('db_'+label)
 if not cmd(label+'_database',[codeql,'database','create',database,'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17000'],src,task,2400):return None
 output=OUT/task['case']/(label+'.sarif')
 if not cmd(label+'_analyze',[codeql,'database','analyze',database,query,'--format=sarif-latest','--output='+str(output),'--threads=4','--ram=17000'],src,task,1500):return None
 return hits(output,task['rule'])
save()
try:
 scratch=Path(tempfile.mkdtemp(prefix='p2two_new_'+os.environ['SLURM_JOB_ID']+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 codeql=Path.home()/'tools/codeql/codeql'
 queryroot=Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11'
 assert codeql.is_file() and queryroot.is_dir()
 for c in CASES:
  ident=str(c['id']);folder=OUT/ident;folder.mkdir()
  rec={'case':ident,'repo':c['repo'],'rule':c['id_rule'],'base':c['base'],'head':c['head'],'patch_hash':c['sha'],'status':'RUNNING','steps':[],'full_functionality':'UNVERIFIED','historical_positive':'UNVERIFIED'}
  S['cases'][ident]=rec;save()
  try:
   p=folder/c['patch']
   for i,filename in enumerate(c['chunks']):
    assert cmd('write_patch_part_'+str(i),['python3',STAGE/filename,p],folder,rec,60),'staging error'
   assert hashfile(p)==c['sha'],'Mismatch original uploaded patch hash'
   rec['modified_files']=re.findall(r'^\+\+\+ b/(\S+)$',p.read_text(),re.M)
   rec['patch_verified']=True;save()
   sub=scratch/ident;sub.mkdir()
   archive=sub/'base.tar.gz';dl('https://codeload.github.com/'+c['repo']+'/tar.gz/'+c['base'],archive)
   assert hashfile(archive)==c['archive_sha'],'Frozen source SHA mismatch'
   base=sub/'base';rec['frozen_regular_file_count']=untar(archive,base)
   patched=sub/'patched';shutil.copytree(base,patched,symlinks=True)
   applies=cmd('git_apply_check',['git','apply','--check',p],patched,rec,90)
   rec['patch_applies']=applies;save()
   if not applies:
    rec['status']='INVALID_PATCH';continue
   assert cmd('git_apply',['git','apply',p],patched,rec,90)
   candidates=[q for q in queryroot.rglob(c['query']) if ('@id '+c['id_rule']) in q.read_text(errors='replace')]
   assert len(candidates)==1,repr(candidates)
   query=candidates[0];rec['query_sha256']=hashfile(query);rec['query_path']=str(query)
   basehits=evaluate('base',base,rec,query,sub)
   genhits=evaluate('generated',patched,rec,query,sub)
   rec['base_alerts']=len(basehits) if basehits is not None else None
   rec['generated_alerts']=len(genhits) if genhits is not None else None
   if basehits is not None and genhits is not None:
    added=new(basehits,genhits)
    rec['generated_new_alerts']=added
    changed=set(rec['modified_files'])
    attributed=[a for a in added if a['path'] in changed or any(a['path'].endswith('/'+p) for p in changed)]
    rec['generated_new_attributed_alerts']=attributed
    rec['generated_target_positive']=bool(attributed)
   try:
    htar=sub/'head.tar.gz';dl('https://codeload.github.com/'+c['repo']+'/tar.gz/'+c['head'],htar)
    hist=sub/'history';untar(htar,hist)
    hithits=evaluate('historical',hist,rec,query,sub)
    rec['historical_head_alerts']=len(hithits) if hithits is not None else None
    if basehits is not None and hithits is not None:
     rec['historical_new_alerts']=new(basehits,hithits)
     rec['historical_positive']='YES' if rec['historical_new_alerts'] else 'NO_NEW_ALERT'
   except Exception as exc:rec['historical_error']=repr(exc)[:600]
   save()
   env=os.environ.copy();env['CI']='1';env['npm_config_cache']=str(sub/'npm-cache')
   if c['id']==21942:
    bun=str(Path.home()/'.bun/bin/bun')
    installed=cmd('bun_frozen_install',[bun,'install','--frozen-lockfile','--ignore-scripts'],patched,rec,420,env)
    rec['tests']='PASS' if installed and cmd('codex_plugin_tests',[bun,'test','__tests__/codex-plugin.test.ts'],patched,rec,750,env) else 'FAIL_OR_UNAVAILABLE'
   else:
    npm=str(Path.home()/'tools/node/bin/npm')
    installed=cmd('manager_npm_ci',[npm,'--prefix','homerail_manager','ci','--ignore-scripts','--no-audit','--no-fund'],patched,rec,1100,env)
    rec['tests']='PASS' if installed and cmd('pr_review_scenario',[npm,'--prefix','homerail_manager','exec','--','vitest','run','tests/pr-review-scenario.test.ts'],patched,rec,900,env) else 'FAIL_OR_UNAVAILABLE'
   rec['full_functionality']='UNVERIFIED__FOCUSED_TESTS_ONLY'
   rec['status']='DONE';save()
   print('CASE_DONE',ident,json.dumps({k:rec.get(k) for k in ['patch_applies','base_alerts','generated_alerts','generated_target_positive','historical_positive','tests']}),flush=True)
  except Exception as exc:
   rec['status']='ERROR';rec['error']=repr(exc)[:800];save()
   print('CASE_ERROR',ident,repr(exc),flush=True)
 S['state']='DONE';save()
except Exception as exc:
 S['state']='INFRA_ERROR';S['fatal_error']=repr(exc)[:700];save();raise
finally:
 try:
  bundle=OUT/'TWO_CASES_ALL_EVIDENCE.zip'
  with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
   for f in sorted(OUT.rglob('*')):
    if f.is_file() and f!=bundle:z.write(f,f.relative_to(OUT))
  print('BUNDLE',bundle,'SHA256',hashfile(bundle),flush=True)
 except Exception as ex:print('BUNDLE_ERROR',repr(ex),flush=True)
PY
