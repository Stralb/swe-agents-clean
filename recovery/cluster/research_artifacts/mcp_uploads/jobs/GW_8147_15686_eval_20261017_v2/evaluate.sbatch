#!/bin/bash
#SBATCH --job-name=GWTWOcases
#SBATCH --partition=batch
#SBATCH --array=0-3
#SBATCH --cpus-per-task=6
#SBATCH --mem=20G
#SBATCH --time=00:40:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import os,pathlib,zipfile,subprocess,hashlib,json,tempfile,shutil,time,re
root=pathlib.Path.home()/'research_artifacts/prevention_pilot_phase2'
source=root/'screen5_blind_batch_job70117'
ids=[8147,8147,15686,15686]
variants=['file2','file3','file1','file2']
orders=[3,3,4,4]
basejobs=[70128,70128,70129,70129]
tests=['src/agent/file-mentions.test.ts','src/agent/file-mentions.test.ts','src/lib/__tests__/github-token.test.ts','src/lib/__tests__/github-token.test.ts']
rules=['js/file-system-race','js/file-system-race','js/file-access-to-http','js/file-access-to-http']
expects=['d61e728507be986de67b0ad982d7c8eb2c0d4a34fd5b39706106642166dc0665','f492373b3ef2d8e4a285d6c3a385168accd0d7b6c1e5894db35152d8ea9aecba','243b9917cfef33482f6f604435b9cb4276150d03122eb1f15c0f3f887d522c7f','aa48be2ebb58556b82706eb789fa3d76628ba4e8124052b613b4dc6b43a476ba']
i=int(os.environ['SLURM_ARRAY_TASK_ID']);case=ids[i];rule=rules[i]
out=root/('GW_screeneval_case%d_%s_job%s'%(case,variants[i],os.environ['SLURM_JOB_ID']))
out.mkdir(exist_ok=True)
result={'case_id':case,'variant':variants[i],'treatment':'UNKNOWN_FROM_FILENAME','target_rule':rule,'state':'started','checks':{}}
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
 stage=pathlib.Path.home()/('research_artifacts/mcp_uploads/screen2_GW_oct17_2026/CASE%d_%s.patch.txt'%(case,variants[i]))
 assert stage.is_file(),'staged patch missing'
 patch=out/'generated.patch';patch.write_bytes(stage.read_bytes())
 result['patch_sha256']=hashlib.sha256(patch.read_bytes()).hexdigest()
 assert result['patch_sha256']==expects[i],'uploaded patch bytes mismatch'
 temp=pathlib.Path(tempfile.mkdtemp(prefix='screen5_'+str(case)+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 f=source/('CASE_%02d_%d.zip'%(orders[i],case))
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
 shutil.copyfile(root/('screen5_eval_%d_job%d'%(case,basejobs[i]))/'base.sarif',out/'base.sarif')
 for label,repo in [('patched',treated)]:
  db=out/('db_'+label)
  if not run('db_'+label,[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(repo),'--overwrite','--threads=6','--ram=18500'],repo,1250):
   raise RuntimeError('CodeQL database create failed: '+label)
  if not run('scan_'+label,[codeql,'database','analyze',db]+query_arg+['--format=sarif-latest','--output',out/(label+'.sarif'),'--threads=6','--ram=18500'],repo,1650):
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
 testfile=treated/tests[i]
 result['focused_test_file_present']=testfile.is_file()
 if result['focused_test_file_present']:
  bun=str(pathlib.Path.home()/'.bun/bin/bun')
  result['bun_install_pass']=run('bun_install',[bun,'install','--ignore-scripts','--frozen-lockfile'],treated,480)
  if result['bun_install_pass']:
   result['focused_test_pass']=run('focused_test',[bun,'x','vitest','run',tests[i]],treated,350)
   result['typecheck_pass']=run('typecheck',[bun,'x','tsc','--noEmit'],treated,450)
 persist()
 print(json.dumps({k:result.get(k) for k in ['case_id','state','patch_apply','query_file','base_target_count','patched_target_count','introduced_target_count']}),flush=True)
except BaseException as e:
 if result['state'] not in ['COMPLETE','patch_did_not_apply']:
  result['state']='ERROR';result['error']=str(e)[:700];persist()
 print('END',case,result['state'],str(e)[:350],flush=True)
PY
