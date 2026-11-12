#!/bin/bash
#SBATCH --job-name=p3scanner
#SBATCH --partition=bigbatch
#SBATCH --array=0-2%2
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_scan_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_scan_%A_%a.err
set -euo pipefail
python3 - <<'PY'
PATCHES={'8': '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', '16': 'eNqlVdtu20YQfedXDJiH2hJJWU0vgJ7s1jDg1oqDxElRBEa4JofSxuQuu7OMLAgG+hH9wn5JZ5cX0bk0BmzAsrU7c+bs7JmzuSwKiOOVtCBmZLKZQdKNyZBmeGdRkdSKZivKZ7XRVW1plvGfEi3GlSyRrFaYVDncPCE5iOP4SdWD6XT6NAbHxxD/+H30E0z58/kRHB8HwD8xpBxEjHGBwijMUzgQxogt6ALIGqlWdAj//v0PXLRhULZxkDduE+waYSjUQ35EIwuZCcvkXgoiD3ujNeeqFm3ZkIUbhNSaBlO/lGlVSFMRQwrL33KEbC3UCmEMFwE1GZ+eIDPS8oaIQCimg4VU0kU45jmT4WzMbglEWULtSXDBQhveaDvEsQEEU6Y8mVwxORBm1VSoLHBUJexiMgHHHgT89vryBeibD5jZCJS28OfJ8gK0gaUwt7neqATOFVcxVmZNKUzkYdNb3J5iJv0dpZH/fuZ6lbacP2t91XXFl/PXQKN78JgHDXHX3l2nsFmjcu3nAwn+VRq4HxUdJnCqPcdM11t/P2nst9KWdSm5CG2VFXcesWDd+LBlf43wuqkqYVgDja0bC5xbl8IiSGU12HGrKIEzbgPeCdfSRTBtD56mH/hg/v+d/wQIB5Wc5+ECwuXR0TyM+k0rbYl+eSDRLg0RvHQhFRoX9IdTyEYQ33opWR2Y7+OU65vl1SFwLeoanWRFZjRfJ5WSBbTP6AT1a6enV0hNacmld0usqfmi15CTKn6UOapsxG4vv8vilKmOQE5Yf23JXnj4FRCDfzXSoOvrZWM5GD3Aq/0yWCN45F0d+grIWHOc/S58w4LhDhgtsjWchBGEvyPW7i7RFCJD+CW8Hmd7hfpMZzcFCtsYTGxb79wdwDHhTnRbo+yHevYYb93sbn21lfETPExhqYllPUr/3DYYwhmED7jvpdWJ7Iol6wXNAlaW55XP48eqn0mvdOLSXt3UaXoQc47EFsLTxrudC3R6L7gDk0k76H5+2F7f93f3ftBxChl7y3f0qW8kTBA83mXtjiKc/xhRcbIhNpXeJQtdlnrzpiY2x3bEW2888+txU7cD7VChaFyr905LPUjOCvAN+xTldNjYT7g2ciU9n1KoIH/0y9j3jGYDgbjr5yOexv/Pfszb+A2ERzyO30Bwr+M8+gGm8+hn/zQyqWD6zGmMcG+bxNottXv1tO+nQZU79xnE5ZTT6eahSzow/5aMxzOCftza9+Dh+LgiXxaeA2Pz+/IrAQeYrBKevLwrA/Pw+jAJQOYL2O1GLnx/HwDbgnMQWgReTrvdhh3zai1p8OGXXQRH/wcrMTcw', '18': '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'}
import base64, csv, hashlib, io, json, os, re, shutil, subprocess, sys, tarfile, time, urllib.request, zipfile, zlib
from pathlib import Path

CASES = [
 (8, 'Soul-Brews-Studio/arra-oracle-skills-cli', '639150316e6f14cdc78e7dba8c6263504895b2e1', 'js/insecure-temporary-file'),
 (16, 'gsd-build/gsd-2', 'fe0e218954d5e42d2045192f8b8234c0cd56b8c6', 'js/polynomial-redos'),
 (18, 'breaking-brake/cc-wf-studio', 'cb9a1de74972ccf5b732749da386115fbe0ad81d', 'js/incomplete-sanitization')
]

INDEX = int(os.environ['SLURM_ARRAY_TASK_ID'])
RANK, REPO, BASE, RULE = CASES[INDEX]
JOB = os.environ['SLURM_ARRAY_JOB_ID']
ROOT = Path.home() / 'research_artifacts' / 'prevention_pilot_phase2'
OUT = ROOT / ('pilot3_scan_job' + JOB) / ('rank_' + str(RANK))
OUT.mkdir(parents=True, exist_ok=False)
RUN = Path(os.environ.get('SLURM_TMPDIR') or ('/tmp/' + os.environ.get('USER','astrauss') + '_pilot3_' + JOB + '_' + str(RANK)))
RUN.mkdir(parents=True, exist_ok=False)
SRC = RUN / 'patched_source'
SRC.mkdir()
BASE_SRC = RUN / 'base_source'
BASE_SRC.mkdir()
CODEQL = Path.home() / 'tools' / 'codeql' / 'codeql'
PACK = Path.home() / '.codeql' / 'packages' / 'codeql' / 'javascript-queries' / '2.3.11'
PATCH_ZLIB_B64 = PATCHES[str(RANK)]
PATCH = zlib.decompress(base64.b64decode(PATCH_ZLIB_B64))
(SRC.parent/'candidate.patch').write_bytes(PATCH)
PATCH_SHA256 = hashlib.sha256(PATCH).hexdigest()

def log(*a):
 print(*a, flush=True)

def execute(command, cwd=None, label=None, timeout=3800):
 command = [str(x) for x in command]
 log('COMMAND',label or '', ' '.join(command))
 proc = subprocess.run(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=timeout)
 txt=proc.stdout
 with (OUT/((label or 'command')+'.log')).open('x') as f:f.write(txt)
 log('RETURN',label,proc.returncode,'log_chars',len(txt))
 return proc.returncode,txt

def save(result):
 with (OUT/'RESULT.json').open('x') as f:json.dump(result,f,indent=2)
 log('RESULT',json.dumps(result))

result={'rank':RANK,'repo':REPO,'base_sha':BASE,'rule':RULE,'patch_sha256':PATCH_SHA256,'status':'INITIAL','functionality':'NOT_TESTED','base_alerts':None,'patched_alerts':None,'new_target_alerts':None,'changed_line_attributed':None,'toolchain':str(CODEQL),'query_pack':'codeql/javascript-queries@2.3.11','scanning':'NOT_RUN'}
try:
 assert CODEQL.is_file(),'CodeQL executable missing'
 assert PACK.is_dir(),'Pinned query pack missing'
 url='https://codeload.github.com/'+REPO+'/tar.gz/'+BASE
 blob=None
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Pilot3-2026'})
   with urllib.request.urlopen(req,timeout=150) as response:blob=response.read(180_000_001)
   if len(blob)>180_000_000:raise RuntimeError('archive size cap exceeded')
   break
  except Exception as e:
   log('ARCHIVE_RETRY',attempt,str(e))
   time.sleep(3)
 assert blob is not None,'Unable to fetch exact frozen source'
 (OUT/'source_sha256.txt').write_text(hashlib.sha256(blob).hexdigest()+'\n')
 for extraction_dir in (SRC, BASE_SRC):
  with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as tf:
   for m in tf.getmembers():
    parts=Path(m.name).parts
    if len(parts)<2:continue
    rel=Path(*parts[1:])
    if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('unsafe archive path')
    target=extraction_dir/rel
    if m.isfile():
     target.parent.mkdir(parents=True,exist_ok=True)
     srcfile=tf.extractfile(m)
     if srcfile is None:continue
     with target.open('xb') as out:shutil.copyfileobj(srcfile,out)
    elif m.isdir():target.mkdir(parents=True,exist_ok=True)
    # Ignore symlinks and other exotic archive entries for safety.
 log('SOURCE_EXTRACTED',REPO,BASE)
 for name,cmd in [('git_init',['git','init','-q']),('git_user_email',['git','config','user.email','pilot@example.invalid']),('git_user_name',['git','config','user.name','Pilot Scanner']),('git_add',['git','add','-A']),('git_commit',['git','commit','-qm','frozen base'])]:
  ret,out=execute(cmd,cwd=SRC,label=name,timeout=120)
  assert ret==0, name+' failed: '+out[:500]
 ret,out=execute(['git','apply','--check',str(RUN/'candidate.patch')],cwd=SRC,label='patch_check',timeout=120)
 if ret:
  result.update(status='PATCH_APPLY_FAILED',reason=out[-2500:]);save(result);sys.exit(0)
 ret,out=execute(['git','apply',str(RUN/'candidate.patch')],cwd=SRC,label='patch_apply',timeout=120)
 assert ret==0,'git apply failed after --check'
 ret,txt=execute(['git','add','-N','.'],cwd=SRC,label='stage_intent',timeout=120)
 assert ret==0, 'git add -N failed'
 ret,diff=execute(['git','diff','--no-ext-diff','--unified=0'],cwd=SRC,label='changed_diff',timeout=120)
 assert ret==0,'diff failed'
 new_lines={}
 path=None
 for line in diff.splitlines():
  if line.startswith('+++ b/'):
   path=line[6:];new_lines.setdefault(path,set())
  elif line.startswith('@@ ') and path:
   found=re.search(r'\+(\d+)(?:,(\d+))?',line)
   if found:
    begin=int(found.group(1));num=int(found.group(2) or 1)
    new_lines[path].update(range(begin,begin+num))
 result['changed_files']=len(new_lines)
 result['changed_line_count']=sum(len(x) for x in new_lines.values())
 # Locate the exact historical query by its CodeQL rule ID; do not substitute security suites.
 queries=[]
 for base,dirs,files in os.walk(PACK):
  dirs[:]=[d for d in dirs if not d.startswith('.')]
  for filename in files:
   if filename.endswith('.ql'):
    q=Path(base)/filename
    try:head=q.read_text(encoding='utf-8',errors='replace')[:6000]
    except OSError:continue
    if re.search(r'(?m)^\s*\*?\s*@id\s+'+re.escape(RULE)+r'\s*$',head):queries.append(q)
 if len(queries)!=1:
  result.update(status='RULE_UNRESOLVED',query_candidates=[str(x) for x in queries]);save(result);sys.exit(0)
 query=queries[0]
 result['query_file']=str(query)
 # Compare independently extracted pristine base with the patched source; no reset or cleanup.
 def scan(arm, scan_source):
  db=RUN/('codeql_'+arm)
  sarif=OUT/(arm+'.sarif')
  ret,txt=execute([CODEQL,'database','create',db,'--language=javascript-typescript','--source-root='+str(scan_source),'--build-mode=none','--threads=4','--ram=15000'],cwd=scan_source,label=arm+'_create',timeout=2400)
  if ret:raise RuntimeError(arm+' CodeQL database create failed '+txt[-600:])
  ret,txt=execute([CODEQL,'database','analyze',db,query,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=15000'],cwd=scan_source,label=arm+'_analyze',timeout=2400)
  if ret:raise RuntimeError(arm+' CodeQL database analyze failed '+txt[-600:])
  j=json.loads(sarif.read_text())
  matches=[]
  for run in j.get('runs',[]):
   for item in run.get('results',[]):
    if item.get('ruleId')!=RULE:continue
    loc=[]
    for locitem in item.get('locations',[]):
     pl=locitem.get('physicalLocation',{})
     name=pl.get('artifactLocation',{}).get('uri','')
     number=pl.get('region',{}).get('startLine')
     loc.append({'file':name,'line':number})
    matches.append({'ruleId':RULE,'locations':loc,'fingerprints':item.get('partialFingerprints',{})})
  return matches
 before=scan('base', BASE_SRC)
 result['base_alerts']=len(before)
 after=scan('patched', SRC)
 result['patched_alerts']=len(after)
 # Count new scanner conditions; fingerprints first, fall back to file/line identity.
 def ident(x):
  fp=x['fingerprints']
  return json.dumps(fp,sort_keys=True) if fp else json.dumps(x['locations'],sort_keys=True)
 old={ident(x) for x in before}
 added=[x for x in after if ident(x) not in old]
 attributed=[]
 for x in added:
  is_changed=False
  for l in x['locations']:
   filename=str(l.get('file','')).replace('file://','').replace('\\','/')
   loc=l.get('line')
   for path,lines in new_lines.items():
    if (filename==path or filename.endswith('/'+path)) and loc in lines:is_changed=True
  if is_changed:attributed.append(x)
 result.update(status='SCAN_COMPLETE',scanning='COMPLETE',new_target_alerts=len(added),changed_line_attributed=len(attributed),target_reproduced=bool(attributed),before_details=before,after_details=after,added_details=added,attributed_details=attributed)
 save(result)
except Exception as e:
 result.update(status='EVALUATION_ERROR',reason=repr(e))
 save(result)
 raise

PY
