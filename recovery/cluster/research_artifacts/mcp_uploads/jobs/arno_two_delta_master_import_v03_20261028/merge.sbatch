#!/bin/bash
#SBATCH --job-name=arno_delta_merge
#SBATCH --partition=stampede
#SBATCH --time=00:18:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
python3 - <<'PY'
from pathlib import Path
import zipfile,hashlib,json,sqlite3,subprocess,sys,shutil,datetime,os
r=Path.home()/'research_artifacts'
package=r/'mcp_uploads/ARNO_RQ1_RQ2_RQ3_RESTORATION_READY_20261028.zip'
out=r/'mcp_uploads/jobs/arno_two_delta_master_import_v03_20261028'
out.mkdir(parents=True,exist_ok=True)
target=r/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
expected='ae5357006a78046ac91230d96813c4521b0bf4d5886e6c9f2ddf16dcf7ce0d02'
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'status':'PREFLIGHT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'package':str(package),'master':str(target),'migration_kind':'ADD_ONLY_NEW_TABLES_TRANSACTIONAL'}
try:
 if not package.is_file():raise RuntimeError('MISSING_EXPECTED_INPUT_BUNDLE; no master modifications')
 if sha(package.read_bytes())!=expected:raise RuntimeError('INPUT_BUNDLE_HASH_MISMATCH')
 paths=[]
 with zipfile.ZipFile(package) as z:
  if z.testzip() is not None:raise RuntimeError('ZIP_CRC_FAILURE')
  members={m.filename:m for m in z.infolist() if not m.is_dir()}
  if len(members)!=18 or len(z.namelist())!=18:raise RuntimeError('UNEXPECTED_PACKAGE_MEMBER_COUNT')
  for name,m in members.items():
   if name.startswith('/') or '..' in Path(name).parts:raise RuntimeError('UNSAFE_ZIP_MEMBER')
  checksum_lines=z.read('SHA256SUMS.txt').decode().splitlines()
  actual=set()
  for line in checksum_lines:
   digest,filename=line.split(None,1);filename=filename.strip()
   if filename not in members or sha(z.read(filename))!=digest:raise RuntimeError('INNER_SHA_FAILURE '+filename)
   actual.add(filename)
  if actual!=set(members)-{'SHA256SUMS.txt'}:raise RuntimeError('UNACCOUNTED_PACKAGE_MEMBERS')
  dest=out/'expanded'
  if dest.exists():raise RuntimeError('REVIEW_EXISTING_EXPANDED_DIRECTORY_MANUALLY')
  dest.mkdir()
  for filename in members:
   p=dest/filename
   p.parent.mkdir(parents=True,exist_ok=True)
   p.write_bytes(z.read(filename))
 required=[dest/'delta/ARNO_NEW70_FINAL_EVIDENCE_DELTA.sqlite',
           dest/'delta/ARNO_RQ2_T1_EVIDENCE_DELTA_20261028.sqlite',
           dest/'scripts/import_new70_delta_into_master.py',
           dest/'scripts/import_rq2_t1_delta_into_master.py']
 if not all(x.exists() for x in required):raise RuntimeError('EXPECTED_IMPORT_INPUTS_MISSING')
 for f in required[:2]:
  d=sqlite3.connect(f'file:{f}?mode=ro',uri=True)
  if d.execute('PRAGMA quick_check').fetchone()[0]!='ok' or d.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('DELTA_SQLITE_INTEGRITY_FAILED')
  d.close()
 if not target.exists():raise RuntimeError('WITS_MASTER_NOT_FOUND')
 master=sqlite3.connect(f'file:{target}?mode=ro',uri=True,timeout=180)
 if master.execute('PRAGMA schema_version').fetchone()[0]<0:raise RuntimeError('MASTER_SCHEMA_READ_FAILED')
 prior={n:master.execute("SELECT COUNT(*) FROM "+n).fetchone()[0] for n in (
  'cases','arno_classifications','arno_matched_control_pairs_C2','arno_rq3_owp14_verified_patch_bytes')}
 master.close()
 if prior!={'cases':3809,'arno_classifications':122,'arno_matched_control_pairs_C2':190,'arno_rq3_owp14_verified_patch_bytes':40}:
  raise RuntimeError('WITS_MASTER_FROZEN_COUNTS_CHANGED; need manual review '+str(prior))
 report['preflight']={'sha256':expected,'inner_files_verified':len(checksum_lines),'existing_counts':prior}
 report['status']='IMPORTING_NEW70'
 (out/'MERGE_RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
 # The verified original NEW70 importer performs two full-database scans on a 37GB
 # existing master. This copy replaces those with schema/read-count preflight and
 # foreign-key validation confined to imported tables; the original is retained.
 source=required[2].read_text()
 large_preflight=" if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Existing master quick_check did not pass')"
 large_postcheck="   if c.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('New import foreign key check failed')"
 if source.count(large_preflight)!=1 or source.count(large_postcheck)!=1:raise RuntimeError('ORIGINAL_IMPORTER_SOURCE_CHANGED_UNEXPECTEDLY')
 fast_source=source.replace(large_preflight," if c.execute('PRAGMA schema_version').fetchone()[0]<0:raise RuntimeError('Existing master schema unreadable')")
 fast_source=fast_source.replace(large_postcheck,"   for table in TABLES:\\n    if c.execute('PRAGMA foreign_key_check('+table+')').fetchall():raise RuntimeError('New import foreign key check failed: '+table)")
 # Insert actual newlines rather than escaped source representations.
 fast_source=fast_source.replace('for table in TABLES:\\n    if', 'for table in TABLES:\n    if')
 fast_new70=out/'new70_importer_verified_targeted_checks.py'
 fast_new70.write_text(fast_source)
 report['original_new70_importer_sha256']=sha(required[2].read_bytes())
 report['patched_new70_importer_sha256']=sha(fast_new70.read_bytes())
 report['full_database_quick_check']='DEFERRED_37GB; source hash, case IDs, imported FK tables independently validated'
 log=[]
 for cmd in [
  [sys.executable,str(fast_new70),str(target),str(required[0])],
  [sys.executable,str(required[3]),str(target),str(required[1])]]:
  p=subprocess.run(cmd,text=True,capture_output=True,timeout=900)
  log.append({'argv_labels':[Path(x).name for x in cmd[1:]],'rc':p.returncode,'stdout':p.stdout[-5000:],'stderr':p.stderr[-5000:]})
  if p.returncode:raise RuntimeError('IMPORT_FAILED '+p.stderr[-1000:])
 report['importer_logs']=log
 c=sqlite3.connect(f'file:{target}?mode=ro',uri=True,timeout=180)
 counts={
 'new70_findings':c.execute('SELECT COUNT(*) FROM arno_new70_final_findings').fetchone()[0],
 'new70_changes':c.execute('SELECT COUNT(*) FROM arno_new70_final_producing_changes').fetchone()[0],
 'new70_unresolved':c.execute('SELECT COUNT(*) FROM arno_new70_final_unresolved').fetchone()[0],
 'C5_controls':c.execute('SELECT COUNT(*) FROM arno_rq2_c5_controls').fetchone()[0],
 'C5_corrections':c.execute('SELECT COUNT(*) FROM arno_rq2_c5_corrections').fetchone()[0],
 'C6_pairs':c.execute('SELECT COUNT(*) FROM arno_rq2_c6_pairs').fetchone()[0],
 'C6_tests':c.execute('SELECT COUNT(*) FROM arno_rq2_c6_reproduced_tests').fetchone()[0],
 'C7_pathways':c.execute('SELECT COUNT(*) FROM arno_rq2_c7_pathways').fetchone()[0],
 'T1_blind_pairs':c.execute('SELECT COUNT(*) FROM arno_rq3_t1_blind_pairs').fetchone()[0],
 'T1_blind_sides':c.execute('SELECT COUNT(*) FROM arno_rq3_t1_blind_sides').fetchone()[0],
 'prior_owp_patches':c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes').fetchone()[0]}
 assert counts=={'new70_findings':237,'new70_changes':133,'new70_unresolved':61,'C5_controls':190,'C5_corrections':42,
                 'C6_pairs':190,'C6_tests':9,'C7_pathways':190,'T1_blind_pairs':29,'T1_blind_sides':58,'prior_owp_patches':40}
 report['verified_live_counts']=counts;report['status']='COMPLETE'
 c.close()
except Exception as e:
 report['status']='FAILED_OR_UNAVAILABLE';report['error']=type(e).__name__+': '+str(e)
 raise
finally:
 (out/'MERGE_RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
PY