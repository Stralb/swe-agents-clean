#!/bin/bash
#SBATCH --job-name=arno_new70_prelim
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import csv,json,hashlib,zlib,sqlite3,collections,datetime
root=Path.home()/'research_artifacts'
source=Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/manual-review/new70-step1/Step1_Canonical_Findings_NEW70.csv'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_new70_prelim_import_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'status':'STARTED','scope':'Pre-QC NEW70 canonical candidate source; not final 237-case findings'}
try:
 raw=source.read_bytes()
 with source.open(encoding='utf-8-sig',newline='') as f:
  rows=list(csv.DictReader(f))
 cand={r['Canonical Finding ID']:r for r in rows}
 if len(rows)!=len(cand)!=254:
  raise ValueError('Incorrect unique source rows')
 conn=sqlite3.connect(str(db),timeout=60)
 conn.execute('PRAGMA busy_timeout=60000')
 conn.execute('PRAGMA foreign_keys=ON')
 linked=list(conn.execute("SELECT canonical_finding_id,case_id FROM arno_canonical_id_pc_links WHERE cohort='new70'"))
 if len(linked)!=176:raise ValueError('Frozen final provenance links missing')
 mismatches=[(cf,case,int(cand[cf]['Case ID'])) for cf,case in linked if cf in cand and int(cand[cf]['Case ID'])!=case]
 exact=[(cf,case) for cf,case in linked if cf in cand and int(cand[cf]['Case ID'])==case]
 if len(mismatches)!=87 or len(exact)!=89:
   raise ValueError('Expected audited 87 mismatches/89 ID+case matches, got '+str((len(mismatches),len(exact))))
 conn.execute('''CREATE TABLE arno_new70_canonical_prelim_254(
    preliminary_finding_id TEXT PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    qc_status TEXT,
    finding_family TEXT, rule_id TEXT, canonical_finding TEXT,
    scanner TEXT, raw_scanner_row_count INTEGER,
    original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    freeze_status TEXT NOT NULL DEFAULT 'PRE_QC_NOT_FINAL'
 )''')
 conn.execute('''CREATE TABLE arno_new70_id_version_conflicts(
    preliminary_finding_id TEXT PRIMARY KEY REFERENCES arno_new70_canonical_prelim_254(preliminary_finding_id),
    preliminary_case_id INTEGER NOT NULL REFERENCES cases(id),
    later_provenance_case_id INTEGER NOT NULL REFERENCES cases(id),
    id_collision_status TEXT NOT NULL,
    audit_source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 )''')
 key='new70_pre_qc_canonical_254'
 conn.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
    key,'pre_qc_canonical_csv','NEW70 preliminary Step1 254 candidates',
    str(source),hashlib.sha256(raw).hexdigest(),'zlib/bytes',zlib.compress(raw,9),
    '254_CANDIDATES_NOT_FINAL',
    '17-record difference versus historical 237 final remains unresolved; do not equate preliminary IDs with later provenance IDs'))
 for r in rows:
  conn.execute('INSERT INTO arno_new70_canonical_prelim_254 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
    r['Canonical Finding ID'],int(r['Case ID']),r['QC Status'],r['Finding Family'],
    r['Rule ID'],r['Canonical Finding'],r['Scanner(s)'],
    int(r['Raw Scanner Row Count']) if r.get('Raw Scanner Row Count') else None,
    json.dumps(r,ensure_ascii=False,sort_keys=True),key,'PRE_QC_NOT_FINAL'))
 for cf,late,early in mismatches:
  conn.execute('INSERT INTO arno_new70_id_version_conflicts VALUES(?,?,?,?,?)',(
     cf,early,late,'SAME_ID_DIFFERENT_CASE_STOP_JOIN',key))
 conn.execute("UPDATE arno_stage_ledger SET detail=detail||'; 254 preliminary NEW70 canonical candidates preserved separately (87 cross-version ID/case conflicts); 237 final rows still missing',last_updated_utc=? WHERE stage_number=4",(
  datetime.datetime.now(datetime.timezone.utc).isoformat(),))
 conn.commit()
 report['counts']={
   'preliminary_candidates':conn.execute('SELECT COUNT(*) FROM arno_new70_canonical_prelim_254').fetchone()[0],
   'explicit_cross_version_conflicts':conn.execute('SELECT COUNT(*) FROM arno_new70_id_version_conflicts').fetchone()[0],
   'accepted_pre_qc':conn.execute("SELECT COUNT(*) FROM arno_new70_canonical_prelim_254 WHERE qc_status='Accepted'").fetchone()[0],
   'needs_manual_qc_pre_qc':conn.execute("SELECT COUNT(*) FROM arno_new70_canonical_prelim_254 WHERE qc_status='Needs manual QC'").fetchone()[0]}
 report['source_sha256']=hashlib.sha256(raw).hexdigest()
 report['blob_roundtrip_ok']=hashlib.sha256(zlib.decompress(conn.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(key,)).fetchone()[0])).hexdigest()==report['source_sha256']
 report['foreign_key_violations']=sum(len(conn.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ('arno_new70_canonical_prelim_254','arno_new70_id_version_conflicts'))
 conn.close()
 if report['counts']!={'preliminary_candidates':254,'explicit_cross_version_conflicts':87,'accepted_pre_qc':176,'needs_manual_qc_pre_qc':78} or not report['blob_roundtrip_ok'] or report['foreign_key_violations']:
  raise ValueError('Post-import integrity mismatch')
 report['status']='COMPLETE'
except Exception as ex:
 report['status']='FAILED';report['error']=type(ex).__name__+': '+str(ex)
 raise
finally:
 (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
PY