#!/bin/bash
#SBATCH --job-name=p2mincase21942
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
python3 - <<'PY'
from pathlib import Path
import hashlib, json, os, zipfile
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
source=root/'case21942_p1_packet_job70075/CASE21942_P1_ISSUE_ONLY.zip'
out=root/('case21942_p2_packet_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True)
dest=out/'CASE21942_P2_MINIMAL_HINT.zip'
sha=lambda b:hashlib.sha256(b).hexdigest()
p1sha='c02858dc6a9cdc3251640e9b9231dd9f104b04505cdcd7b2b7627a6e9b3cfa0f'
raw=source.read_bytes()
assert sha(raw)==p1sha,'P1 ZIP SHA mismatch'
old=b'Use secure temporary-file and directory creation, including in tests.'
new=b'Use secure temporary directories.'
with zipfile.ZipFile(source,'r') as z:
 original_issue=z.read('ISSUE.md')
 assert original_issue.count(old)==1 and new not in original_issue
 p2_issue=original_issue.replace(old,new)
 with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as outzip:
  for member in z.infolist():
   data=p2_issue if member.filename=='ISSUE.md' else z.read(member)
   info=zipfile.ZipInfo(member.filename,date_time=(1980,1,1,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED
   info.create_system=member.create_system
   info.external_attr=member.external_attr
   outzip.writestr(info,data)
with zipfile.ZipFile(source,'r') as p1,zipfile.ZipFile(dest,'r') as p2:
 assert p2.testzip() is None
 assert set(p1.namelist())==set(p2.namelist())
 different=[name for name in p1.namelist() if p1.read(name)!=p2.read(name)]
 assert different==['ISSUE.md'],different
 assert len(p2.namelist())==249
 record={'study':'CASE21942_P2_HINT_MINIMIZATION','control_O1_target_new_warnings':2,
 'P1_target_new_warnings':0,'P1_hint':old.decode(),'P2_hint':new.decode(),
 'only_changed_from_P1':'ISSUE.md','unchanged_other_files':248,
 'zip_sha256':sha(dest.read_bytes()),'zip_bytes':dest.stat().st_size,
 'baseline_case':'Soul-Brews-Studio/arra-oracle-skills-cli issue 372',
 'frozen_base':'639150316e6f14cdc78e7dba8c6263504895b2e1',
 'prompt':'Implement the issue in ISSUE.md using the repository in REPO/. Make the changes you consider necessary, and return a complete Git unified diff relative to REPO/ as a downloadable .patch file. Work only from these supplied files; do not consult other commits or PRs.',
 'interpretation':'Exploratory one-shot arm; requires independent repetitions'}
(out/'P2_MANIFEST.json').write_text(json.dumps(record,indent=2)+'\n')
print('READY',json.dumps({'file':str(dest),'sha256':record['zip_sha256'],'bytes':record['zip_bytes'],'changed':different}),flush=True)
PY
