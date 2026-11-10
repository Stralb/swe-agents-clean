#!/usr/bin/env python3
"""Idempotent, transaction-safe merge of the validated NEW70 evidence delta into the existing master.

Usage: python import_new70_delta_into_master.py /path/to/ARNO_RESEARCH_MASTER.sqlite /path/to/ARNO_NEW70_FINAL_EVIDENCE_DELTA.sqlite

Never rebuilds the master. Never overwrites older preliminary NEW70 records or existing analysis tables.
Creates only new arno_new70_final_* tables and the frozen evidence view.
"""
import sqlite3,sys,json,hashlib,zlib,datetime
from pathlib import Path
TABLES=[
 'arno_new70_final_source_blobs',
 'arno_new70_final_findings',
 'arno_new70_final_producing_changes',
 'arno_new70_final_raw_finding_links',
 'arno_new70_final_finding_maps',
 'arno_new70_final_unresolved',
 'arno_new70_final_source_id_audit',
 'arno_new70_final_method_qc',
 'arno_new70_final_freeze_manifest',
]
VIEW='arno_v_new70_finding_change_evidence'
SIZES={'arno_new70_final_findings':237,'arno_new70_final_producing_changes':133,'arno_new70_final_raw_finding_links':255,'arno_new70_final_finding_maps':237,'arno_new70_final_unresolved':61,'arno_new70_final_source_id_audit':237,'arno_new70_final_source_blobs':20}
sha=lambda b:hashlib.sha256(b).hexdigest()
def run(master,delta):
 master=Path(master).expanduser().resolve();delta=Path(delta).expanduser().resolve()
 if not master.is_file() or not delta.is_file() or master==delta:raise RuntimeError('Master and delta must be separate existing files.')
 c=sqlite3.connect(str(master),timeout=180)
 c.execute('PRAGMA foreign_keys=ON')
 c.execute('PRAGMA busy_timeout=180000')
 if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Existing master quick_check did not pass')
 c.execute('ATTACH DATABASE ? AS delta',(f'file:{delta}?mode=ro',))
 try:
  source_tables={x[0] for x in c.execute("SELECT name FROM delta.sqlite_master WHERE type='table'")}
  if not set(TABLES).issubset(source_tables):raise RuntimeError('Required frozen delta tables absent')
  missing=[t for t in TABLES if c.execute("SELECT COUNT(*) FROM main.sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()[0]==0]
  present=[t for t in TABLES if t not in missing]
  if missing and present:raise RuntimeError('Partial NEW70 final import detected; refusing to overwrite or repair without audit')
  if 'cases' not in {x[0] for x in c.execute("SELECT name FROM main.sqlite_master WHERE type='table'")}:raise RuntimeError('Existing master has no cases table')
  ids={r[0] for r in c.execute('SELECT case_id FROM delta.arno_new70_final_findings')}
  valid={r[0] for r in c.execute('SELECT id FROM main.cases WHERE id IN ('+','.join('?'*len(ids))+')',tuple(sorted(ids)))}
  if valid!=ids:raise RuntimeError('Canonical source case IDs not found in master: '+str(sorted(ids-valid)))
  for name,expected in SIZES.items():
   n=c.execute('SELECT COUNT(*) FROM delta.'+name).fetchone()[0]
   if n!=expected:raise RuntimeError(f'Delta count mismatch {name}: {n} vs {expected}')
  if c.execute('PRAGMA delta.foreign_key_check').fetchall():raise RuntimeError('Delta foreign keys invalid')
  if not all(sha(zlib.decompress(b))==h for b,h in c.execute('SELECT content_zlib,sha256 FROM delta.arno_new70_final_source_blobs')):raise RuntimeError('Delta original archive bytes did not match SHA256')
  if present:
   for table in TABLES:
    if c.execute('SELECT COUNT(*) FROM main.'+table).fetchone()[0]!=c.execute('SELECT COUNT(*) FROM delta.'+table).fetchone()[0]:raise RuntimeError('Existing final table count drift: '+table)
   mainhash={r[0]:r[1] for r in c.execute('SELECT source_key,sha256 FROM main.arno_new70_final_source_blobs')}
   deltahash={r[0]:r[1] for r in c.execute('SELECT source_key,sha256 FROM delta.arno_new70_final_source_blobs')}
   if mainhash!=deltahash:raise RuntimeError('Existing final source hash mismatch')
   print(json.dumps({'status':'ALREADY_IMPORTED_VERIFIED','tables':len(TABLES),'findings':237,'producing_changes':133,'case_ids_cross_checked':len(ids)}))
   return
  # SQLite ATTACH is used only to read a local, independently audited delta.
  # The master receives new tables only. Its earlier data is not changed.
  c.execute('BEGIN IMMEDIATE')
  try:
   for table in TABLES:
    sql=c.execute("SELECT sql FROM delta.sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]
    if not sql.startswith('CREATE TABLE '+table+' '):raise RuntimeError('Unexpected delta schema: '+table)
    c.execute(sql)
    ncols=len(c.execute('PRAGMA table_info('+table+')').fetchall())
    rows=c.execute('SELECT * FROM delta.'+table).fetchall()
    c.executemany('INSERT INTO main.'+table+' VALUES('+','.join('?'*ncols)+')',rows)
   schema=c.execute("SELECT sql FROM delta.sqlite_master WHERE type='view' AND name=?",(VIEW,)).fetchone()[0]
   c.execute(schema)
   c.execute('''CREATE TABLE arno_new70_final_publication_status (
    claim_key TEXT PRIMARY KEY,rq TEXT NOT NULL,verification TEXT NOT NULL,
    claim_text TEXT NOT NULL,source_table TEXT NOT NULL,qualifications TEXT NOT NULL,
    replaces_prior_missing_artifact_flag INTEGER NOT NULL)''')
   state=[
    ('NEW70_FINAL_237','RQ1','FROZEN_INPUT_REPRODUCED','237 canonical findings; 255 raw links, 18 duplicate raw representations collapsed','arno_new70_final_findings','Scanner findings, not confirmed vulnerabilities; frozen QC does not establish independent human review.',1),
    ('NEW70_MAPPED_176','RQ1','FROZEN_INPUT_REPRODUCED','176/237 findings mapped to 133 concrete producing changes in 69 cases','arno_new70_final_finding_maps','No intent or causal model-choice attribution established by Phase 6.',1),
    ('NEW70_NOT_ISOLATED_61','RQ1','EXPLICIT_SOURCE_LIMITATION','61 findings in case 17701 not isolated because of OSV base/head materialization asymmetry','arno_new70_final_unresolved','These are retained canonical findings, not mapped producing changes; Trivy base/head unchanged.',1),
    ('NEW70_PHASE7','RQ1','SEPARATE_DOWNSTREAM_PROVENANCE_REQUIRED','Phase 6 file itself does not contain Direct / Side-effect / Unclear judgments','arno_new70_final_freeze_manifest','Link independently frozen Phase 7 source rather than inventing it.',0),
   ]
   c.executemany('INSERT INTO arno_new70_final_publication_status VALUES(?,?,?,?,?,?,?)',state)
   if c.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('New import foreign key check failed')
   c.commit()
  except:
   c.rollback();raise
  result={'status':'IMPORTED_VERIFIED','master':str(master),'delta':str(delta),'new_tables':len(TABLES)+1,'new_view':VIEW,
          'canonical_findings':237,'raw_links':255,'finding_maps':237,'mapped':176,'not_isolated':61,
          'producing_changes':133,'master_case_ids_confirmed':len(ids),
          'older_tables_unchanged':True,'source_hashes_verified':True,'stage_ledger_untouched':True}
  print(json.dumps(result,indent=2))
 finally:c.close()
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('Usage: python import_new70_delta_into_master.py MASTER.sqlite NEW70_DELTA.sqlite')
 run(sys.argv[1],sys.argv[2])
