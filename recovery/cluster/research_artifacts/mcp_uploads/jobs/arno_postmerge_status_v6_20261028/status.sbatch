#!/bin/bash
#SBATCH --job-name=arno_postmerge_status
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=1G
python3 - <<'PY'
from pathlib import Path
import sqlite3,json,datetime
r=Path.home()/'research_artifacts'
out=r/'mcp_uploads/jobs/arno_postmerge_status_v6_20261028'
out.mkdir(parents=True,exist_ok=True)
db=r/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
c=sqlite3.connect(str(db),timeout=150)
c.execute('PRAGMA busy_timeout=150000')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
expected={'arno_new70_final_findings':237,'arno_new70_final_producing_changes':133,
'arno_new70_final_unresolved':61,'arno_rq2_c5_controls':190,
'arno_rq2_c5_corrections':42,'arno_rq2_c6_pairs':190,
'arno_rq2_c6_reproduced_tests':9,'arno_rq2_c7_pathways':190,
'arno_rq3_t1_blind_pairs':29,'arno_rq3_t1_blind_sides':58,
'arno_rq3_owp14_verified_patch_bytes':40}
for name,n in expected.items():
 if c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]!=n:raise RuntimeError('Postmerge count mismatch: '+name)
if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_postmerge_publication_readiness_20261028'").fetchone()[0]:raise RuntimeError('Snapshot already exists; no overwrite')
rows=[
('RQ1_NEW70','RQ1','IMPORTED_SOURCE_VERIFIED','237 canonical findings, 133 producing changes, 61 explicitly not isolated',
 'arno_new70_final_findings; arno_new70_final_source_blobs','These are scanner findings; no independently verified human adjudication established.'),
('RQ1_NON_M_ROOTS','RQ1','SOURCE_GAP','233 final M roots preserved, final decisions for 109 other roots not independently confirmed',
 'arno_d7_final_M_roots_233; arno_root_decisions','Do not treat root census as final adjudication.'),
('RQ2_C5_C6','RQ2','IMPORTED_AND_PVALUES_REPRODUCED','190 controls, 42 QC corrections, 190 frozen pairs, nine primary p-values',
 'arno_rq2_c5_controls; arno_rq2_c6_pairs; arno_rq2_c6_reproduced_tests','Frozen C5/C6 context digest discrepancy; bootstrap intervals not independently rerun.'),
('RQ2_HUMAN','RQ2','INDEPENDENT_REVIEW_UNVERIFIED','Within-pipeline corrections preserved',
 'arno_rq2_c5_corrections','Human reviewer identity and independent blind adjudication not established.'),
('RQ3_OWP','RQ3','ORIGINAL_PATCH_AND_SCANNER_IDENTITY_VERIFIED','40 matched patch-scan hashes; 12 matched triples; 21/10/15 O/W/P new warnings',
 'arno_rq3_owp14_verified_patch_bytes; arno_rq3_owp14_run_scans','Full functional acceptance and causal interpretation not established.'),
('RQ3_T1','RQ3','BLIND_SELECTION_IMPORTED','29 blind pairs and 58 sides imported',
 'arno_rq3_t1_blind_pairs; arno_rq3_t1_blind_sides','Do not equate eligibility screening with tested generation functionality.'),
('RQ3_REPAIR','RQ3','HISTORICALLY_REPORTED_CHAIN_INCOMPLETE','3/7 to 7/7 targeted repair scanner-negative reported',
 'mcp_uploads/seven_minimal_info_intake_20261020; prevention_pilot_phase2','Final repair hashes and independent functional validation still require joins.')]
try:
 c.execute('BEGIN IMMEDIATE')
 c.execute('''CREATE TABLE arno_postmerge_publication_readiness_20261028(
   audit_key TEXT PRIMARY KEY,rq TEXT NOT NULL,evidence_status TEXT NOT NULL,
   quantitative_summary TEXT NOT NULL,original_evidence_locator TEXT NOT NULL,
   publication_qualification TEXT NOT NULL,verified_at_utc TEXT NOT NULL)''')
 c.executemany('INSERT INTO arno_postmerge_publication_readiness_20261028 VALUES(?,?,?,?,?,?,?)',[(*row,now) for row in rows])
 updates={3:'Final NEW70 237 finding records/133 PCs/61 not isolated now imported and source-hash verified (2026-10-28).',
          4:'Final NEW70 canonical finding-to-producing-change evidence and raw links now imported; prior broad attributions preserved.',
          7:'C5 190 completed control records and 42 QC corrections; C6 190 comparison pairs and nine reproduced tests now imported; independent human review not established.'}
 for stage,note in updates.items():
  old=c.execute('SELECT detail FROM arno_stage_ledger WHERE stage_number=?',(stage,)).fetchone()
  if old is None:raise RuntimeError('Ledger row missing: '+str(stage))
  if note not in old[0]:
   c.execute("UPDATE arno_stage_ledger SET detail=detail||?,last_updated_utc=? WHERE stage_number=?",('; '+note,now,stage))
 c.commit()
except:
 c.rollback();raise
receipt={'status':'COMPLETE','snapshot_rows':c.execute('SELECT COUNT(*) FROM arno_postmerge_publication_readiness_20261028').fetchone()[0],
         'stage_notes_updated':[3,4,7],'old_claim_history_preserved':True,
         'master_counts':expected}
c.close()
(out/'POSTMERGE_STATUS_REPORT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
PY