#!/bin/bash
#SBATCH --job-name=arno_peerreview_source_status
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=1G
python3 - <<'PY'
from pathlib import Path
import sqlite3,datetime,json
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_peerreview_source_status_v6_20261028'
O.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(str(R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'),timeout=120)
c.execute('PRAGMA busy_timeout=120000')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert c.execute('SELECT COUNT(*) FROM arno_d7_final_M_roots_233').fetchone()[0]==233
assert c.execute('SELECT COUNT(*) FROM arno_seven_final_repair_case_evidence').fetchone()[0]==7
assert c.execute('SELECT COUNT(*) FROM arno_c6_independent_bootstrap_replication').fetchone()[0]==9
if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_peerreview_recovery_audit_v6_20261028'").fetchone()[0]:raise ValueError('Audit table already exists')
rows=[
('D7_FULL_342','RQ1','LIBRARY_INDEXED_TEXT_CROSSCHECKED_NOT_RAW_IMPORTED',
 'Library /Arno Research Stuff/D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv',
 '342 unique rows, 36 columns; M233,H6,T103,U0; M233 matched existing Wits M rows exactly on seven classification/adjudication fields.',
 'Library extracted text is not byte-equivalent to original CSV; final H/T/U rows must be imported from original bytes to make master self-contained.'),
('D_FINAL_AI_CODING','RQ1','FROZEN_MODEL_CODING_METADATA_LOCATED',
 'Library /Arno Research Stuff/D_FINAL_METADATA_GPT56SOL_v1.0.json; D_FINAL_SUMMARY_GPT56SOL_v1.0.md',
 'Two isolated GPT-5.6 Sol coding passes; root route agreement 337/342, kappa 0.9669; M explanation tier agreement 88/232, kappa 0.0933; mandatory D4 198 roots.',
 'This is AI repeated blind coding, not two independent humans; adjudication does not establish independent human validation.'),
('SEVEN_FINAL_SOURCE','RQ3','FULL_ORIGINAL_ARCHIVE_IN_MASTER_HASH_MATCHED',
 'arno_seven_final_repair_archive; arno_seven_final_repair_case_evidence',
 'Original 104 MB seven-case handoff preserved in SQLite; all seven exact final patch and scanner-result hashes verified; seven scanner-negative final outputs.',
 'No 7/7 proof of prospective prevention: two researcher-authored repairs, missing full functionality, potential detector bypass and test-fixture changes.'),
('C6_BOOTSTRAP','RQ2','INDEPENDENT_NUMERICAL_REPRODUCTION_IN_MASTER',
 'arno_c6_independent_bootstrap_replication; arno_c6_bootstrap_reproduction_artifacts',
 'Nine point estimates exactly reproduced; 95 repository components, 5,000 seeded bootstrap replicates; maximum confidence-bound difference 0.00476.',
 'Original RNG stream/algorithm not packaged; independent numerical reproduction, not byte-identical original.'),
('C6_CONTEXT','RQ2','DOCUMENTED_RECODING_HASH_NOT_RESOLVED',
 'C6_CONTEXT_QC_CORRECTIONS.csv; Library original C5 context and C6 docs in arno_evidence_assets',
 'One GitHub API 404 was recoded from No to missing for control case 12897 during C6; no semantic C5 label changed.',
 'C6 context digest differs from C5 original; no byte-identical C6 transformed context recovered.'),
('HUMAN_REVIEW','ALL','NOT_ESTABLISHED',
 'arno_rq2_c5_corrections; arno_d7_final_M_roots_233; original D metadata',
 'AI assistance, repeated model coding, frozen QC and researcher-authored targeted repairs are separately identifiable.',
 'Do not present AI coding or QC corrections as independent human adjudication without signed records.')
]
c.execute('BEGIN IMMEDIATE')
try:
 c.execute('''CREATE TABLE arno_peerreview_recovery_audit_v6_20261028(
  evidence_key TEXT PRIMARY KEY,rq TEXT NOT NULL,status TEXT NOT NULL,
  source_locator TEXT NOT NULL,verified_fact TEXT NOT NULL,
  limitation TEXT NOT NULL,audited_at_utc TEXT NOT NULL)''')
 c.executemany('INSERT INTO arno_peerreview_recovery_audit_v6_20261028 VALUES(?,?,?,?,?,?,?)',[(*r,now) for r in rows])
 c.commit()
except:
 c.rollback();raise
result={'status':'COMPLETE','rows':c.execute('SELECT COUNT(*) FROM arno_peerreview_recovery_audit_v6_20261028').fetchone()[0],
        'source_data_not_modified':True,
        'recorded_gaps':[r[0] for r in rows if 'NOT_' in r[2] or 'HASH_NOT_RESOLVED' in r[2]]}
c.close()
(O/'AUDIT_ENTRY_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY