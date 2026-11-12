#!/bin/bash
#SBATCH --job-name=p3scanfix
#SBATCH --partition=bigbatch
#SBATCH --array=0-2%2
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_scan_fix_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_scan_fix_%A_%a.err
set -euo pipefail
# Run exclusively on compute nodes. Keep all previous outputs untouched.
# Prefer existing cluster Node.js; fall back to official binary within this job's scratch.
if ! command -v node >/dev/null 2>&1; then
  if [ -r /etc/profile.d/modules.sh ]; then source /etc/profile.d/modules.sh || true; fi
  if command -v module >/dev/null 2>&1; then
    module load nodejs 2>/dev/null || module load node 2>/dev/null || true
  fi
fi
if ! command -v node >/dev/null 2>&1; then
  for NODEBIN in "$HOME/.nvm/versions/node"/*/bin/node "$HOME/.local/share/mise/installs/node"/*/bin/node "$HOME/miniconda3/bin/node" "$HOME/tools/node/bin/node" /usr/local/bin/node /usr/bin/node; do
    if [ -x "$NODEBIN" ]; then export PATH="$(dirname "$NODEBIN"):$PATH"; break; fi
  done
fi
if ! command -v node >/dev/null 2>&1; then
  export PILOT_NODE_SCRATCH="${SLURM_TMPDIR:-/tmp}/astrauss_pilot3_node_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
  mkdir -p "$PILOT_NODE_SCRATCH"
  # Only download and unpack on the allocated compute node, never on login.
  python3 - <<'NODE_FETCH'
import hashlib, os, pathlib, urllib.request, tarfile
root=pathlib.Path(os.environ['PILOT_NODE_SCRATCH'])
version='v22.16.0'
filename=f'node-{version}-linux-x64.tar.xz'
base=f'https://nodejs.org/dist/{version}/'
headers={'User-Agent':'Wits-research-pilot3-evaluation'}
def get(url):
  with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120) as r:
    return r.read()
checksums=get(base+'SHASUMS256.txt').decode()
expected=next(line.split()[0] for line in checksums.splitlines() if line.split()[-1]==filename)
data=get(base+filename)
assert hashlib.sha256(data).hexdigest()==expected, 'Node.js archive SHA-256 mismatch'
archive=root/filename
archive.write_bytes(data)
with tarfile.open(archive,'r:xz') as tf:
  for entry in tf.getmembers():
    target=(root/entry.name).resolve()
    assert target.is_relative_to(root.resolve()), 'Invalid archive path'
  tf.extractall(root,filter='data')
print('NODE_READY',root/filename,'verified_sha256',expected)
NODE_FETCH
  export PATH="$PILOT_NODE_SCRATCH/node-v22.16.0-linux-x64/bin:$PATH"
fi
node --version
python3 - <<'PY'
PATCHES={'8': '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'}
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
OUT = ROOT / ('pilot3_intscan_job' + JOB) / ('rank_' + str(RANK))
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
