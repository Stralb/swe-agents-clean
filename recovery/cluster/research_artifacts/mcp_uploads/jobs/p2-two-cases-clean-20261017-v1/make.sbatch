#!/bin/bash
#SBATCH --job-name=p2twofull
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:35:00
set -euo pipefail
python3 - <<'PY'
import hashlib,io,json,os,pathlib,shutil,stat,tarfile,time,urllib.request,zipfile
from pathlib import Path
home=Path.home(); root=home/'research_artifacts/prevention_pilot_phase2'
out=root/('two_new_clean_baselines_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True);assert not any(out.iterdir())
source=root/'case_screen_issue_recovery_v1_job69671/RESEARCHER_CORPUS_ISSUES_24.json'
data=json.loads(source.read_text())
specs=[
 {'rank':8,'case':21942,'repo':'Soul-Brews-Studio/arra-oracle-skills-cli','issue':372,'pr':388,'base':'639150316e6f14cdc78e7dba8c6263504895b2e1','issue_hash':'f04cf054cf45ad7e55366000d223affcf916010c2046ebc488cf7e2d28db247d'},
 {'rank':4,'case':16392,'repo':'xiaotianfotos/homerail','issue':181,'pr':189,'base':'e3d9382886a07dce4df7ff4aaedffd9613a09a4d','issue_hash':'2b13cdb6c8fb125d72f3fb902dce73b21c647c55a972b7ac771f92c7a013e20d'}
]
sha=lambda b:hashlib.sha256(b).hexdigest()
def download(url):
 for n in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Phase2-Blind'})
   with urllib.request.urlopen(req,timeout=180) as f:raw=f.read(90_000_001)
   if len(raw)>90_000_000:raise ValueError('archive too large')
   return raw
  except Exception:
   if n==2:raise
   time.sleep(5)
def zi(name,mode=stat.S_IFREG|0o644):
 z=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));z.create_system=3;z.compress_type=zipfile.ZIP_DEFLATED;z.external_attr=(mode<<16);return z
manifest=[]
outer=out/'PHASE2_TWO_NEW_CASES_ONE_ZIP.zip'
common_prompt='Implement the issue in ISSUE.md using the repository in REPO/. Make the changes you consider necessary, and return a complete Git unified diff relative to REPO/ as a downloadable .patch file. Work only from these supplied files; do not consult other commits or PRs.\n'
with zipfile.ZipFile(outer,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
 for i,spec in enumerate(specs,1):
  matches=[r for r in data['records'] if r.get('source_index')==2 and r.get('queue_rank')==spec['rank'] and r.get('case_id')==spec['case'] and r.get('case_found')]
  assert len(matches)==1;rec=matches[0]
  assert rec['repository']==spec['repo'] and rec['issue_number']==spec['issue'] and rec['pr_number']==spec['pr']
  assert rec['issue_body_sha256']==spec['issue_hash'] and sha(rec['issue_body'].encode())==spec['issue_hash']
  assert rec['pr_base_sha']==spec['base'] and rec['base_matches_live_pr']
  assert rec['pre_pr_issue_body_chronology_supported'] and rec['body_temporal_verdict']=='NO_RECORDED_POST_PR_UPDATE'
  url='https://codeload.github.com/'+spec['repo']+'/tar.gz/'+spec['base']
  tarbytes=download(url)
  source_hash=sha(tarbytes)
  names=set();cnt=0;symlink=0
  issue=rec['issue_title']+'\n\n'+rec['issue_body'].rstrip('\n')+'\n'
  innerbuf=io.BytesIO()
  with tarfile.open(fileobj=io.BytesIO(tarbytes),mode='r:gz') as tar,zipfile.ZipFile(innerbuf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as inner:
   inner.writestr(zi('ISSUE.md'),issue.encode())
   for member in tar:
    parts=pathlib.PurePosixPath(member.name).parts
    if len(parts)<2:continue
    rel=pathlib.PurePosixPath(*parts[1:])
    assert not rel.is_absolute() and '..' not in rel.parts and chr(92) not in str(rel)
    name='REPO/'+str(rel)
    if member.isdir():continue
    assert name not in names; names.add(name)
    if member.isfile():
     assert member.size<35_000_000
     cnt+=1;file=tar.extractfile(member);assert file
     blob=file.read();assert len(blob)==member.size
     inner.writestr(zi(name,stat.S_IFREG|(member.mode&0o777)),blob)
    elif member.issym():
     symlink+=1;inner.writestr(zi(name,stat.S_IFLNK|0o777),member.linkname.encode())
    else:raise ValueError('Unsupported file type: '+name)
  assert cnt>30
  innerbytes=innerbuf.getvalue()
  with zipfile.ZipFile(io.BytesIO(innerbytes),'r') as verify:
   assert verify.testzip() is None and len(verify.namelist())==cnt+symlink+1
   assert verify.read('ISSUE.md')==issue.encode()
  dirname='CASE_'+str(i)+'_'+str(spec['case'])
  innername='SOURCE_'+str(spec['case'])+'.zip'
  bundle.writestr(dirname+'/'+innername,innerbytes,compress_type=zipfile.ZIP_STORED)
  bundle.writestr(dirname+'/PROMPT.txt',common_prompt)
  meta={'case_id':spec['case'],'rank':spec['rank'],'repo':spec['repo'],'issue':spec['issue'],'historical_pr':spec['pr'],'base_sha':spec['base'],'source_count':cnt,'source_symlinks':symlink,'issue_snapshot_status':'NO_RECORDED_POST_PR_UPDATE','source_archive_sha256':source_hash,'inner_zip_sha256':sha(innerbytes),'issue_title':rec['issue_title']}
  manifest.append(meta)
  print('CASE_READY',json.dumps(meta),flush=True)
 readme="""TWO CLEAN BASELINE CASES - ONE DOWNLOAD

The outer bundle has TWO separate, blinded case ZIPs and their prompts.
Never attach the outer ZIP to a fresh generation chat; it contains both cases.
Extract outer ZIP, then:
  CASE_1_21942/SOURCE_21942.zip + CASE_1_21942/PROMPT.txt
  CASE_2_16392/SOURCE_16392.zip + CASE_2_16392/PROMPT.txt

Run each in a separate fresh Temporary Chat outside research Project.
Do not mention historical PR or warnings. Same model and effort.
Return two .patch files to original research chat.
Case labels and PRs are researcher-side only.

Issue-body timestamps support pre-PR origin; timestamps cannot prove byte-for-byte unchanged issue bodies.
Historical positive base-vs-head warning reproduction still needs explicit
case-specific confirmation before causal claims.
"""
 bundle.writestr('README_FIRST.txt',readme)
 bundle.writestr('RESEARCHER_ONLY_CASE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(outer) as z:assert z.testzip() is None and len(z.namelist())==6
result={'job_id':os.environ['SLURM_JOB_ID'],'file':str(outer),'sha256':sha(outer.read_bytes()),'bytes':outer.stat().st_size,'cases':manifest}
(out/'PACKAGING_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print('BUNDLE_READY',json.dumps({'file':str(outer),'sha256':result['sha256'],'size':result['bytes']}),flush=True)
PY
