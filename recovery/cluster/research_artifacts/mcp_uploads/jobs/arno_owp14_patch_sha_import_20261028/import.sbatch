#!/bin/bash
#SBATCH --job-name=arno_owp14_patches
#SBATCH --partition=stampede
#SBATCH --time=00:09:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import json,sqlite3,io,re,base64,zipfile,hashlib,zlib,datetime
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_owp14_patch_sha_import_20261028'
D.mkdir(parents=True,exist_ok=True)
DB=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'status':'STARTED','scope':'Exact O/W/P original patch bytes matched by SHA256 against 40 previously imported scanner arm RESULT.json records; no functionality inference.'}
try:
  inputs=[('O','mcp_uploads/owp14_20261018_transfer_v1',6,12),
          ('W','mcp_uploads/owp14_w14_20261018_transfer_v1',5,14),
          ('P','mcp_uploads/owp14_user_p14_20261018_transfer_v1',4,14)]
  archives=[];patches=[]
  for arm,folder,n,expectedn in inputs:
    fs=sorted((R/folder).glob('chunk_*.txt'))
    if len(fs)!=n:raise ValueError('Fragment count mismatch '+arm)
    for i,f in enumerate(fs,1):
      if f.name!=f'chunk_{i:02d}.txt':raise ValueError('Discontinuous chunk names')
    source=re.sub(rb'\s+',b'',b''.join(x.read_bytes() for x in fs))
    zip_bytes=base64.b64decode(source,validate=True)
    members=[]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
      if z.testzip() is not None:raise ValueError('ZIP CRC validation failed '+arm)
      for m in z.infolist():
        if m.is_dir():continue
        found=re.fullmatch(r'CASE_([0-9]+)_([OWP])\.patch',m.filename)
        if not found or found.group(2)!=arm:raise ValueError('Unexpected archive member '+m.filename)
        cid=int(found.group(1))
        b=z.read(m.filename)
        if not b or len(b)>3000000:raise ValueError('Unexpected patch size')
        patches.append((cid,arm,m.filename,b,sha(b)))
        members.append(m.filename)
    if len(members)!=expectedn or len(set(members))!=expectedn:raise ValueError('Archive count mismatch '+arm)
    archives.append((arm,zip_bytes,sha(zip_bytes),json.dumps([str(f.relative_to(R)) for f in fs])))
  if len(patches)!=40 or len({(x[0],x[1]) for x in patches})!=40:raise ValueError('Patch uniqueness/count error')
  c=sqlite3.connect(str(DB),timeout=180)
  c.execute('PRAGMA busy_timeout=180000')
  c.execute('PRAGMA foreign_keys=ON')
  old={(i,a):h for i,a,h in c.execute('SELECT case_id,arm,patch_sha256 FROM arno_rq3_owp14_run_scans')}
  if len(old)!=40 or set(old)!={(x[0],x[1]) for x in patches}:raise ValueError('Scanner-run membership differs from uploaded patch archives')
  for cid,arm,filename,b,h in patches:
    if old[cid,arm]!=h:raise ValueError('Scanner patch hash mismatch '+str(cid)+'/'+arm)
  prior={t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'arno_rq3_owp14_verified_patch_bytes' in prior:raise ValueError('Refusing overwrite: patch bytes already imported')
  c.execute('BEGIN IMMEDIATE')
  c.execute('''CREATE TABLE arno_rq3_owp14_verified_archive(
     arm TEXT PRIMARY KEY CHECK(arm IN ('O','W','P')),original_zip_sha256 TEXT NOT NULL,
     source_fragment_paths_json TEXT NOT NULL,original_zip_bytes INTEGER NOT NULL,
     zip_zlib BLOB NOT NULL,verification_status TEXT NOT NULL)''')
  c.execute('''CREATE TABLE arno_rq3_owp14_verified_patch_bytes(
     case_id INTEGER NOT NULL,arm TEXT NOT NULL,original_filename TEXT NOT NULL,
     patch_sha256 TEXT NOT NULL,original_patch_bytes INTEGER NOT NULL,patch_zlib BLOB NOT NULL,
     patch_header_present INTEGER NOT NULL,verification_status TEXT NOT NULL,
     PRIMARY KEY(case_id,arm),
     FOREIGN KEY(case_id,arm) REFERENCES arno_rq3_owp14_run_scans(case_id,arm),
     FOREIGN KEY(arm) REFERENCES arno_rq3_owp14_verified_archive(arm))''')
  for arm,b,h,paths in archives:
    c.execute('INSERT INTO arno_rq3_owp14_verified_archive VALUES(?,?,?,?,?,?)',(arm,h,paths,len(b),zlib.compress(b,9),'BASE64_ZIP_CRC_AND_SHA256_VERIFIED'))
  for cid,arm,filename,b,h in patches:
    c.execute('INSERT INTO arno_rq3_owp14_verified_patch_bytes VALUES(?,?,?,?,?,?,?,?)',
      (cid,arm,filename,h,len(b),zlib.compress(b,9),int(b'diff --git ' in b[:500]),'EXACT_SHA256_MATCH_TO_SCANNER_RESULT'))
  c.execute("UPDATE arno_rq3_owp14_run_scans SET patch_bytes_match_status='ORIGINAL_PATCH_BYTES_SHA256_MATCH_SCANNER_RESULT' WHERE patch_bytes_match_status='HASH_RECORDED_GENERATED_PATCH_BYTES_NOT_INDEPENDENTLY_MATCHED'")
  if c.execute("SELECT COUNT(*) FROM arno_rq3_owp14_run_scans WHERE patch_bytes_match_status='ORIGINAL_PATCH_BYTES_SHA256_MATCH_SCANNER_RESULT'").fetchone()[0]!=40:raise ValueError('Unexpected patch status changes')
  c.execute('INSERT INTO arno_rq3_owp14_reproduction_checks VALUES(?,?,?,?,?)',(
    'OWP14_PATCH_BYTES_EXACT_HASH_LINK','40','40','EXACT_SHA256_MATCH_REPRODUCED','All 40 patch bytes matched to case+arm scanner records; functional equivalence not established'))
  for t in ['arno_rq3_owp14_verified_archive','arno_rq3_owp14_verified_patch_bytes']:
    if c.execute('PRAGMA foreign_key_check('+t+')').fetchall():raise ValueError('Foreign-key errors in '+t)
  c.commit()
  q={'patches':c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes').fetchone()[0],
     'archives':c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_archive').fetchone()[0],
     'patch_sha_roundtrip':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT patch_sha256,patch_zlib FROM arno_rq3_owp14_verified_patch_bytes')),
     'zip_sha_roundtrip':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT original_zip_sha256,zip_zlib FROM arno_rq3_owp14_verified_archive')),
     'patches_with_git_header':c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes WHERE patch_header_present=1').fetchone()[0]}
  if not q['patch_sha_roundtrip'] or not q['zip_sha_roundtrip']:raise ValueError('Post-commit SHA mismatch')
  report['counts']=q;report['status']='COMPLETE';c.close()
except Exception as e:
  report['status']='FAILED';report['error']=type(e).__name__+': '+str(e);raise
finally:
  (D/'PATCH_IMPORT_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(report,indent=2),flush=True)
PY