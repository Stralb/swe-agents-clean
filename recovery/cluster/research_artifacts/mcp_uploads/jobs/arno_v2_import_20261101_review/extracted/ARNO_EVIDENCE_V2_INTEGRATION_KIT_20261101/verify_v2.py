#!/usr/bin/env python3
"""Read-only independent post-import QA; no writes to source or v2."""
import argparse, hashlib, json, sqlite3, zlib
p=argparse.ArgumentParser();p.add_argument('database');args=p.parse_args()
c=sqlite3.connect('file:'+args.database+'?mode=ro',uri=True)
checks={
 'study_runs':('SELECT count(*) FROM study_runs',94),
 'v2_evidence_runs':('SELECT count(*) FROM arno_v2_run_evidence',33),
 'archive_crosswalk':('SELECT count(*) FROM arno_v2_archive_patch_crosswalk',255),
 'archive_only':('SELECT count(*) FROM arno_v2_archive_patch_crosswalk WHERE indexed_in_master=0',150),
 'posthoc_repairs':('SELECT count(*) FROM arno_v2_legacy_patch_crosswalk',7),
 'missing_AC_prompt_rows':("SELECT count(*) FROM arno_v2_coverage_gaps WHERE gap_id LIKE 'PROMPT_%'",12)
}
for name,(sql,n) in checks.items():
 actual=c.execute(sql).fetchone()[0];assert actual==n,(name,actual,n)
for cond,total in [('P1',15),('P2',10),('P3',10)]:
 actual=c.execute('SELECT sum(introduced_count) FROM arno_v2_run_evidence WHERE cohort=? AND arm=?',('OCT2026_P123_NEW_RETROSPECTIVE',cond)).fetchone()[0]
 assert actual==total,(cond,actual,total)
count=0
for run,role,expected,compressed in c.execute('SELECT run_id,role,sha256,zlib_blob FROM arno_v2_evidence_bytes'):
 actual=hashlib.sha256(zlib.decompress(compressed)).hexdigest()
 assert actual==expected,(run,role);count+=1
bad=c.execute('PRAGMA foreign_key_check').fetchall();assert not bad,bad
print(json.dumps({'status':'PASS','verified_embedded_assets':count,'checks':{k:v[1] for k,v in checks.items()}},indent=2))
