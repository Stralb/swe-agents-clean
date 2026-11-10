#!/usr/bin/env python3
from pathlib import Path,PurePosixPath
from collections import Counter
import hashlib,json,os,subprocess,tempfile,zipfile,shutil,time,traceback
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
source=root/'owp14_allcases_packets_job71014/CASE_32759_O.zip'
stage=Path.home()/'research_artifacts/mcp_uploads/jobs/case32759_fresh5_20261019b'
out=root/('case32759_fresh5_scan_job'+os.environ.get('SLURM_JOB_ID','unknown'))
out.mkdir(exist_ok=False)
suite='codeql/javascript-queries:codeql-suites/javascript-security-extended.qls'
codeql=Path.home()/'tools/codeql/codeql'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='2dce5a0132cadb85b779bcd032e81b5aadc95bfafce391e8437916fb400399f2'
assert '2.25.6' in subprocess.check_output([str(codeql),'version'],text=True)
def run(name,cmd,cwd):
 with (out/(name+'.log')).open('w') as f:
  r=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
 if r.returncode:raise RuntimeError(name+' rc='+str(r.returncode))
def findings(p):
 result=[]
 for r in json.loads(p.read_text()).get('runs',[]):
  for x in r.get('results',[]):
   loc=(x.get('locations') or [{}])[0].get('physicalLocation',{})
   result.append(dict(rule=x.get('ruleId',''),path=loc.get('artifactLocation',{}).get('uri',''),line=loc.get('region',{}).get('startLine'),message=x.get('message',{}).get('text',''),fp=x.get('partialFingerprints') or {}))
 return result
def delta(before,after,strong):
 def key(x):
  if strong:return (x['rule'],x['path'],x['fp'].get('primaryLocationLineHash') or x['message'],x['fp'].get('primaryLocationStartColumnFingerprint') or '')
  return (x['rule'],x['path'],x['message'])
 count=Counter(key(x) for x in before);new=[]
 for x in after:
  k=key(x)
  if count[k]:count[k]-=1
  else:new.append({y:v for y,v in x.items() if y!='fp'})
 return new
scratch=Path(tempfile.mkdtemp(prefix='c32759_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
rows=[]
try:
 base=scratch/'base';base.mkdir()
 with zipfile.ZipFile(source) as z:
  names=[x for x in z.namelist() if x.startswith('REPO/') and not x.endswith('/')]
  assert len(names)==23
  for name in names:
   parts=PurePosixPath(name).parts
   assert '..' not in parts
   f=base.joinpath(*parts[1:]);f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(name))
 db=scratch/'db_base'
 run('db_base',[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(base),'--threads=3','--ram=10000'],base)
 run('scan_base',[codeql,'database','analyze',db,suite,'--format=sarif-latest','--output='+str(out/'base.sarif'),'--threads=3','--ram=10000'],base)
 before=findings(out/'base.sarif')
 for arm in ['A0','A2','A3','A4','A5']:
  result={'arm':arm,'stage':'START','baseline_count':len(before),'codeql':'2.25.6'}
  target=out/arm;target.mkdir()
  try:
   patch=target/('CASE_32759_'+arm+'_r01.patch')
   run('prepare_'+arm,['python3',stage/('input_'+arm+'.py'),target],base)
   repo=scratch/arm;shutil.copytree(base,repo)
   run('check_'+arm,['git','apply','--check',patch],repo)
   run('apply_'+arm,['git','apply',patch],repo)
   db=scratch/('db_'+arm)
   run('db_'+arm,[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(repo),'--threads=3','--ram=10000'],repo)
   run('scan_'+arm,[codeql,'database','analyze',db,suite,'--format=sarif-latest','--output='+str(target/'after.sarif'),'--threads=3','--ram=10000'],repo)
   after=findings(target/'after.sarif');strong=delta(before,after,True);weak=delta(before,after,False)
   result.update(stage='SCAN_COMPLETE',after_count=len(after),new_strong_count=len(strong),new_weak_count=len(weak),new_strong=strong,new_weak=weak)
  except Exception as e:result.update(stage='ERROR',error=repr(e),traceback=traceback.format_exc()[-1700:])
  (target/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
  rows.append(result);(out/'SUMMARY.json').write_text(json.dumps(rows,indent=2)+'\n')
  print(arm,result['stage'],result.get('new_strong_count'),flush=True)
finally:shutil.rmtree(scratch,ignore_errors=True)
