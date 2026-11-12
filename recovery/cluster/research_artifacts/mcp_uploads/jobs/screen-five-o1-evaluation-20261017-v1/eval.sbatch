#!/bin/bash
#SBATCH --job-name=screen5O
#SBATCH --partition=batch
#SBATCH --array=0-4
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=00:30:00
python3 - <<'PY'
import os,pathlib,zipfile,subprocess,hashlib,json,tempfile,shutil,time,re
root=pathlib.Path.home()/'research_artifacts/prevention_pilot_phase2'
source=root/'screen5_blind_batch_job70117'
ids=[7680,17062,8147,15686,334]
rules=['js/http-to-file-access','js/polynomial-redos','js/file-system-race','js/file-access-to-http','js/polynomial-redos']
expects=['ae1c2910f67bd53f4f78ff7d988da28b5724c38645da5c0233a8de770e1c6407','232d759be845fdc93b4dfc0ff875a975982106447e5fb63c25e2d1ef9f672636','4141508ec822c1cd8669aa8a9ef80cc376081e284b147db4b2013ab7335bf6e7','4e46570dbdae5537543ae9b828d9315b2abed9800709ebe5132cf46686cce7b2','08c3e81c2ba82e9285fb0b0084b4696805e8a64fb059c7222ba4d0e030af74f9']
i=int(os.environ['SLURM_ARRAY_TASK_ID']);case=ids[i];rule=rules[i]
out=root/('screen5_eval_'+str(case)+'_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True)
result={'case_id':case,'target_rule':rule,'state':'started','checks':{}}
def persist():
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
def run(label,cmd,cwd=None,timeout=480):
 with (out/(label+'.log')).open('w') as log:
  try:
   p=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
   result['checks'][label]={'returncode':p.returncode}
   persist()
   return p.returncode==0
  except Exception as e:
   result['checks'][label]={'error':str(e)[:350]}
   persist()
   return False
try:
 parts=[]
 for n in range(20):
  f=pathlib.Path.home()/('research_artifacts/mcp_uploads/screen_five_o1_20261017_v1/CASE_%d_%02d.txt'%(case,n))
  if not f.exists():break
  parts.append(f.read_bytes())
 assert parts,'staged patch absent'
 patch=out/'generated.patch';patch.write_bytes(b''.join(parts))
 result['patch_sha256']=hashlib.sha256(patch.read_bytes()).hexdigest()
 assert result['patch_sha256']==expects[i],'uploaded patch bytes mismatch'
 temp=pathlib.Path(tempfile.mkdtemp(prefix='screen5_'+str(case)+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 f=source/('CASE_%02d_%d.zip'%(i+1,case))
 assert f.is_file()
 with zipfile.ZipFile(f) as z:
  for info in z.infolist():
   if not info.filename.startswith('REPO/'):continue
   pos=pathlib.PurePosixPath(info.filename).parts
   if '..' in pos:raise RuntimeError('unsafe path')
   target=temp/info.filename
   if info.filename.endswith('/'):target.mkdir(parents=True,exist_ok=True);continue
   if (info.external_attr>>16)&0o170000==0o120000:continue
   target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(z.read(info))
 base=temp/'REPO';treated=temp/'TREATED';shutil.copytree(base,treated,symlinks=False)
 result['patch_apply']=run('patch_apply_check',['git','apply','--check',patch],treated,90)
 if not result['patch_apply']:
  result['state']='patch_did_not_apply';persist();raise SystemExit(0)
 assert run('patch_apply',['git','apply',patch],treated,90)
 codeql=pathlib.Path.home()/'tools/codeql/codeql'
 qbase=pathlib.Path.home()/'.codeql/packages/codeql/javascript-queries/2.3.11'
 candidates={'js/polynomial-redos':['Security/CWE-1333/PolynomialRegularExpression.ql','Security/CWE-1333/PolynomialReDoS.ql'],
 'js/file-system-race':['Security/CWE-367/TOCTOU.ql','Security/CWE-367/FileSystemRace.ql'],
 'js/http-to-file-access':['Security/CWE-918/HTTPToFileAccess.ql'],
 'js/file-access-to-http':['Security/CWE-918/FileAccessToHTTP.ql']}
 choices=list(qbase.rglob('*.ql')) if qbase.exists() else []
 query=next((p for p in choices if re.search(r'(?m)^ *\*? *@@id '+re.escape(rule)+r'\s*$',p.read_text(errors='replace'))),None)
 # Default scan complete Javascript security suite when exact standalone file unavailable
 query_arg=[str(query)] if query else ['codeql/javascript-queries:codeql-suites/javascript-security-extended.qls']
 result['query_file']=str(query) if query else 'javascript-security-extended.qls'
 persist()
 if not codeql.exists():raise RuntimeError('CodeQL binary not found')
 for label,repo in [('base',base),('patched',treated)]:
  db=out/('db_'+label)
  if not run('db_'+label,[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root',repo,'--overwrite','--threads=2'],repo,720):
   raise RuntimeError('CodeQL database create failed: '+label)
  if not run('scan_'+label,[codeql,'database','analyze',db]+query_arg+['--format=sarif-latest','--output',out/(label+'.sarif'),'--threads=2','--ram=8192'],repo,720):
   raise RuntimeError('CodeQL analysis failed: '+label)
 def alerts(label):
  sarif=json.loads((out/(label+'.sarif')).read_text())
  hits=[]
  for runitem in sarif.get('runs',[]):
   for z in runitem.get('results',[]):
    rid=z.get('ruleId','')
    if rid!=rule:continue
    loc=z.get('locations',[{}])[0].get('physicalLocation',{})
    region=loc.get('region',{})
    finger=z.get('partialFingerprints',{})
    hits.append({'rule':rid,'uri':loc.get('artifactLocation',{}).get('uri'),'line':region.get('startLine'),'message':z.get('message',{}).get('text','')[:500],'fingerprint':finger})
  return hits
 before,after=alerts('base'),alerts('patched')
 def key(v):
  return(v['uri'],v['fingerprint'].get('primaryLocationLineHash') or v['message'],v['fingerprint'].get('primaryLocationStartColumnFingerprint') or '')
 from collections import Counter
 old=Counter(map(key,before));introduced=[]
 for fnd in after:
  k=key(fnd)
  if old[k]:old[k]-=1
  else:introduced.append(fnd)
 result.update({'state':'COMPLETE','base_target_count':len(before),'patched_target_count':len(after),'introduced_target_count':len(introduced),'introduced_findings':introduced})
 persist()
 print(json.dumps({k:result.get(k) for k in ['case_id','state','patch_apply','query_file','base_target_count','patched_target_count','introduced_target_count']}),flush=True)
except BaseException as e:
 if result['state'] not in ['COMPLETE','patch_did_not_apply']:
  result['state']='ERROR';result['error']=str(e)[:700];persist()
 print('END',case,result['state'],str(e)[:350],flush=True)
PY
