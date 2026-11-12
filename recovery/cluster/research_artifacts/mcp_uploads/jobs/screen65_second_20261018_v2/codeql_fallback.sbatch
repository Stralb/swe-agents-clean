#!/bin/bash
#SBATCH --job-name=screen65_second_codeql
#SBATCH --partition=batch
#SBATCH --array=0-64%6
#SBATCH --cpus-per-task=3
#SBATCH --mem=14G
#SBATCH --time=01:30:00
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export PYTHONUNBUFFERED=1
python3 - <<'PY'
from pathlib import Path,PurePosixPath
from collections import Counter
import os,subprocess,zipfile,json,tempfile,shutil,hashlib,time,traceback
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
stage=root/'screen65_second_20261018_v1'
manifest=json.loads((stage/'TRANSFER_MANIFEST.json').read_text())
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
case=manifest['patches'][i];cid=case['case_id']
out=root/('screen65_second_codeql_job'+os.environ['SLURM_ARRAY_JOB_ID'])
out.mkdir(exist_ok=True)
caseout=out/('CASE_%05d'%cid)
caseout.mkdir(exist_ok=False)
patch=stage/'patches'/('CASE_%05d.patch'%cid)
complete=root/'remaining65_archives_oct17_v1'/('CASE_%05d.zip'%cid)
reduced=root/'remaining65_targeted14_v1'/('CASE_%05d.zip'%cid)
source=complete if complete.exists() else reduced
full=source==complete
status={'case_id':cid,'claimed_status':case['status'],'source_type':'FULL_FROZEN_SNAPSHOT' if full else 'FILTERED_SOURCE_PROVISIONAL',
        'stage':'START','checks':{},'suite':'codeql/javascript-queries:codeql-suites/javascript-security-extended.qls'}
def save():
 (caseout/'RESULT.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
def run(tag,args,cwd,timeout):
 started=time.time()
 with (caseout/(tag+'.log')).open('w') as f:
  try:
   p=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
   status['checks'][tag]={'rc':p.returncode,'seconds':round(time.time()-started,1)}
   save()
   return p.returncode==0
  except Exception as exc:
   status['checks'][tag]={'error':str(exc)[:250],'seconds':round(time.time()-started,1)}
   save()
   return False
def results(path):
 r=json.loads(path.read_text());rows=[]
 for run_obj in r.get('runs',[]):
  for it in run_obj.get('results',[]):
   loc=(it.get('locations') or [{}])[0].get('physicalLocation',{})
   rows.append({'rule':it.get('ruleId',''),'path':loc.get('artifactLocation',{}).get('uri',''),
    'line':loc.get('region',{}).get('startLine'),
    'message':it.get('message',{}).get('text',''),
    'fingerprints':it.get('partialFingerprints') or {}})
 return rows
def compare(before,after,method):
 def key(v):
  if method=='strong':
   return (v['rule'],v['path'],v['fingerprints'].get('primaryLocationLineHash') or v['message'],v['fingerprints'].get('primaryLocationStartColumnFingerprint') or '')
  return (v['rule'],v['path'],v['message'])
 counted=Counter(map(key,before));added=[]
 for v in after:
  k=key(v)
  if counted[k]:counted[k]-=1
  else:added.append(v)
 return added
save()
try:
 assert hashlib.sha256(patch.read_bytes()).hexdigest()==case['sha256'],'PATCH_SHA_MISMATCH'
 assert source.is_file(),'SOURCE_ABSENT'
 scratch=Path(tempfile.mkdtemp(prefix='cq65_%05d_'%cid,dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 repo=scratch/'repo'
 repo.mkdir()
 files=0;total=0
 with zipfile.ZipFile(source) as z:
  for ent in z.infolist():
   if not ent.filename.startswith('REPO/') or ent.is_dir():continue
   rel=PurePosixPath(ent.filename)
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('UNSAFE_ZIP_NAME')
   f=repo.joinpath(*rel.parts[1:])
   f.parent.mkdir(parents=True,exist_ok=True)
   files+=1;total+=ent.file_size
   if files>80000 or total>900*1024*1024:raise ValueError('SOURCE_LIMIT')
   f.write_bytes(z.read(ent))
 status['source_files']=files
 status['stage']='EXTRACTED';save()
 before=scratch/'original'
 shutil.copytree(repo,before,symlinks=True)
 status['stage']='APPLYING';save()
 if not run('apply_check',['git','apply','--check',patch],repo,180):raise RuntimeError('PATCH_DOES_NOT_APPLY')
 if not run('apply',['git','apply',patch],repo,180):raise RuntimeError('PATCH_APPLICATION_FAILED')
 status['stage']='PATCH_APPLIED';save()
 codeql=Path.home()/'tools/codeql/codeql'
 suite=status['suite']
 for name,tree in [('before',before),('after',repo)]:
  db=scratch/('db_'+name)
  status['stage']='DATABASE_'+name.upper();save()
  if not run('database_'+name,[codeql,'database','create',db,'--language=javascript-typescript','--build-mode=none','--source-root='+str(tree),'--threads=3','--ram=11000'],tree,3200):
   raise RuntimeError('DATABASE_'+name.upper()+'_FAILED')
  status['stage']='ANALYZING_'+name.upper();save()
  if not run('analyze_'+name,[codeql,'database','analyze',db,suite,'--format=sarif-latest','--output',caseout/(name+'.sarif'),'--threads=3','--ram=11000'],tree,3600):
   raise RuntimeError('ANALYZE_'+name.upper()+'_FAILED')
 pre=results(caseout/'before.sarif')
 post=results(caseout/'after.sarif')
 added_strong=compare(pre,post,'strong')
 added_weak=compare(pre,post,'weak')
 before_rules=Counter(x['rule'] for x in pre)
 after_rules=Counter(x['rule'] for x in post)
 summary={'before_total':len(pre),'after_total':len(post),'new_strong_count':len(added_strong),
          'new_weak_count':len(added_weak),'new_by_rule_strong':dict(Counter(x['rule'] for x in added_strong)),
          'new_by_rule_weak':dict(Counter(x['rule'] for x in added_weak)),
          'before_by_rule':dict(before_rules),'after_by_rule':dict(after_rules),
          'new_strong_findings':[{'rule':x['rule'],'path':x['path'],'line':x['line'],'message':x['message'][:360]} for x in added_strong],
          'new_weak_findings':[{'rule':x['rule'],'path':x['path'],'line':x['line'],'message':x['message'][:360]} for x in added_weak]}
 status['findings']=summary
 status['stage']='SCAN_COMPLETE'
except BaseException as e:
 status['stage']='ERROR'
 status['error']=repr(e)[:1000]
finally:
 save()
 if 'scratch' in locals(): shutil.rmtree(scratch,ignore_errors=True)
 print('CASE',cid,status['stage'],status.get('findings',{}).get('new_strong_count'),status.get('error',''),flush=True)
PY