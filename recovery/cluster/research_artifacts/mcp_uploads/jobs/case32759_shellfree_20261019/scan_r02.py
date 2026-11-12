#!/usr/bin/env python3
import os,json,hashlib,zipfile,subprocess,tempfile,shutil,traceback
from pathlib import Path,PurePosixPath
from collections import Counter
home=Path.home()/'research_artifacts'
source=home/'prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_32759_O.zip'
stage=home/'mcp_uploads/jobs/case32759_shellfree_20261019'
out=home/('prevention_pilot_phase2/case32759_shellfree_scan_job'+os.environ.get('SLURM_JOB_ID','unknown'))
out.mkdir()
codeql=Path.home()/'tools/codeql/codeql'
suite='codeql/javascript-queries:codeql-suites/javascript-security-extended.qls'
res={'arm':'R02_SHELLFREE','stage':'START','codeql':'2.25.6'}
def cmd(name,args,cwd):
 with (out/(name+'.log')).open('w') as fh:
  p=subprocess.run([str(x) for x in args],cwd=cwd,stdout=fh,stderr=subprocess.STDOUT,timeout=3600)
 if p.returncode:raise RuntimeError(name+' rc='+str(p.returncode))
def alerts(p):
 rows=[]
 for run in json.loads(p.read_text()).get('runs',[]):
  for x in run.get('results',[]):
   loc=(x.get('locations') or [{}])[0].get('physicalLocation',{})
   rows.append({'rule':x.get('ruleId',''),'path':loc.get('artifactLocation',{}).get('uri',''),'line':loc.get('region',{}).get('startLine'),'message':x.get('message',{}).get('text',''),'fp':x.get('partialFingerprints') or {}})
 return rows
def fresh(old,new,strict):
 def key(x):
  if strict:return (x['rule'],x['path'],x['fp'].get('primaryLocationLineHash') or x['message'],x['fp'].get('primaryLocationStartColumnFingerprint') or '')
  return (x['rule'],x['path'],x['message'])
 c=Counter(map(key,old));z=[]
 for x in new:
  k=key(x)
  if c[k]:c[k]-=1
  else:z.append({t:v for t,v in x.items() if t!='fp'})
 return z
scratch=Path(tempfile.mkdtemp(prefix='shellfree_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
try:
 assert hashlib.sha256(source.read_bytes()).hexdigest()=='2dce5a0132cadb85b779bcd032e81b5aadc95bfafce391e8437916fb400399f2'
 assert '2.25.6' in subprocess.check_output([str(codeql),'version'],text=True)
 repo=scratch/'repo';repo.mkdir()
 with zipfile.ZipFile(source) as z:
  names=[n for n in z.namelist() if n.startswith('REPO/') and not n.endswith('/')]
  assert len(names)==23
  for n in names:
   parts=PurePosixPath(n).parts
   assert '..' not in parts
   f=repo.joinpath(*parts[1:]);f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(n))
 cmd('prepare',['python3',stage/'input_R02.py',out],repo)
 patch=out/'CASE_32759_R02_SHELLFREE.patch'
 cmd('apply_check',['git','apply','--check',patch],repo)
 cmd('apply',['git','apply',patch],repo)
 cmd('node_tests',['node','--test',repo/'tests/resolve-codex-program.test.mjs'],repo)
 db=scratch/'db'
 cmd('db',[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(repo),'--threads=3','--ram=10000'],repo)
 target=out/'after.sarif'
 cmd('analyze',[codeql,'database','analyze',db,suite,'--format=sarif-latest','--output='+str(target),'--threads=3','--ram=10000'],repo)
 original=home/'prevention_pilot_phase2/case32759_fresh6_scan_job71754/base.sarif'
 a=alerts(original);b=alerts(target)
 strict=fresh(a,b,True);loose=fresh(a,b,False)
 res.update(stage='SCAN_COMPLETE',before_total=len(a),after_total=len(b),new_strong_count=len(strict),new_conservative_count=len(loose),new_strong_alerts=strict,new_conservative_alerts=loose)
except Exception as e:
 res.update(stage='ERROR',error=str(e),traceback=traceback.format_exc()[-3000:])
finally:
 (out/'RESULT.json').write_text(json.dumps(res,indent=2)+'\n')
 shutil.rmtree(scratch,ignore_errors=True)
print(res['stage'],res.get('new_strong_count'),res.get('error',''),flush=True)
