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
