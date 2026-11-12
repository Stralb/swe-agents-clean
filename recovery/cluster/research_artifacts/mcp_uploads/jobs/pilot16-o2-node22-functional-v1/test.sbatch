#!/bin/bash
#SBATCH --job-name=p2o2node22
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
set -euo pipefail
python3 - <<'PY'
import hashlib,json,os,pathlib,re,shutil,subprocess,tarfile,tempfile,urllib.request,time
from pathlib import Path
base=Path.home()/'research_artifacts/prevention_pilot_phase2'
jid=os.environ['SLURM_JOB_ID']
out=base/('pilot16_O2_tests_node22_job'+jid);out.mkdir(exist_ok=False)
logs=out/'logs';logs.mkdir()
prior=base/'pilot16_O2_eval_job69945'
patch=prior/'PILOT_16_O2.patch'
sha='31cff22de441d70338e7b3a3100db4718ce9a32546435589f3c95cfea5d86c1f'
base_sha='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
tar_sha='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
version='v22.16.0'
report={'protocol':'O2_node22_functionality_verification_v1','case_id':313,'replicate':'O2','frozen_base_sha':base_sha,'patch_sha256':sha,'node_version_target':version,'steps':[],'status':'STARTED','functional_correctness':'NOT_ESTABLISHED'}
def persist(): (out/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
def hashfile(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def record(name,cmd,cwd=None,timeout=1800,env=None,required=False):
 print('START',name,flush=True)
 log=logs/(name+'.log')
 row={'name':name,'log':str(log.relative_to(out)),'cmd':[str(x) for x in cmd]}
 try:
  with log.open('x') as f:r=subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  row['exit_code']=r.returncode
 except subprocess.TimeoutExpired:row['exit_code']=None;row['error']='TIMEOUT'
 except Exception as e:row['exit_code']=None;row['error']=str(e)[:300]
 report['steps'].append(row);persist()
 print('END',name,row.get('exit_code'),flush=True)
 if required and row['exit_code']!=0:raise RuntimeError('FAILED '+name)
 return row['exit_code']==0
def download(url,path,cap):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Reproduction-O2-Node22'})
   with urllib.request.urlopen(req,timeout=180) as r,path.open('xb') as f:
    n=0
    while True:
     block=r.read(1024*1024)
     if not block:break
     n+=len(block)
     if n>cap:raise RuntimeError('download cap exceeded')
     f.write(block)
   return
  except Exception:
   path.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep(3)
persist()
try:
 assert patch.is_file() and hashfile(patch)==sha,'Patch missing or SHA mismatch'
 scratch=Path(tempfile.mkdtemp(prefix='p2_o2node22_'+jid+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 name='node-'+version+'-linux-x64.tar.xz'
 dist=scratch/name
 sums=scratch/'SHASUMS256.txt'
 download('https://nodejs.org/dist/'+version+'/'+name,dist,80000000)
 download('https://nodejs.org/dist/'+version+'/SHASUMS256.txt',sums,120000)
 expected=next((m.group(1) for line in sums.read_text().splitlines() if (m:=re.fullmatch(r'([0-9a-f]{64})\s+'+re.escape(name),line))),None)
 assert expected is not None and hashfile(dist)==expected,'Node release checksum mismatch'
 report['node_distribution_sha256']=expected
 record('extract_node',['tar','-xJf',dist,'-C',scratch],cwd=scratch,timeout=90,required=True)
 nodebin=scratch/('node-'+version+'-linux-x64')/'bin'
 assert (nodebin/'node').is_file() and (nodebin/'npm').exists()
 env=os.environ.copy()
 env['PATH']=str(nodebin)+os.pathsep+env.get('PATH','')
 env['npm_config_cache']=str(scratch/'npm-cache')
 env['CI']='true'
 record('node_version',[nodebin/'node','--version'],scratch,30,env,True)
 record('npm_version',[nodebin/'npm','--version'],scratch,30,env,True)
 tar=scratch/'base.tar.gz'
 download('https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+base_sha,tar,150000000)
 assert hashfile(tar)==tar_sha,'Frozen base archive SHA mismatch'
 src=scratch/'repo';src.mkdir()
 with tarfile.open(tar,'r:gz') as arc:
  for m in arc:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe source tar path')
   dst=src.joinpath(*rel.parts)
   if m.isdir():dst.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    dst.parent.mkdir(parents=True,exist_ok=True)
    with arc.extractfile(m) as inp,dst.open('xb') as f:shutil.copyfileobj(inp,f)
 record('patch_check',['git','apply','--check',patch],src,90,env,True)
 record('patch_apply',['git','apply',patch],src,90,env,True)
 installed=record('npm_ci_node22',[nodebin/'npm','ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],src,2400,env)
 if installed:
  # Keep test selection fixed independently of patch output.
  ok=record('complete_milestone_focus',[nodebin/'node','--import','./src/resources/extensions/gsd/tests/resolve-ts.mjs','--experimental-strip-types','--test','src/resources/extensions/gsd/tests/complete-milestone.test.ts'],src,750,env)
  report['focused_test_status']='PASS' if ok else 'FAIL'
 else:report['focused_test_status']='UNAVAILABLE_DEPENDENCY_INSTALL'
 report['functional_correctness']='NOT_ESTABLISHED__FOCUSED_TESTS_NOT_FULL_TASK_ORACLE'
 report['status']='COMPLETE'
 persist()
 print('FINAL',json.dumps({'focused_test_status':report['focused_test_status'],'functional_correctness':report['functional_correctness']}),flush=True)
except Exception as exc:
 report['status']='FAILED';report['error']=str(exc)[:1200];persist()
 raise
PY
