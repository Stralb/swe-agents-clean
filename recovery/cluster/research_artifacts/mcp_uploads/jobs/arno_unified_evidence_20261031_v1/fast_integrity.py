#!/usr/bin/env python3
"""Bounded independent validity gate for the new full-evidence SQLite."""
import sqlite3,json,hashlib,datetime
from pathlib import Path
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output'
P=O/'ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite'
assert (O/'BACKUP_VERIFICATION.json').exists()
assert (O/'CORE_COUNTS.json').exists()
assert (O/'EVIDENCE_COUNTS.json').exists()
db=sqlite3.connect('file:'+str(P)+'?mode=ro',uri=True,timeout=120)
def n(sql):return db.execute(sql).fetchone()[0]
expected={'study_cases':192,'study_findings':842,'study_producing_changes':455,
'study_classifications':192,'study_roots':342,'study_runs':68,'study_artifacts':633,
'study_human_reviews':50,'study_limitations':12}
found={t:n('SELECT COUNT(*) FROM '+t) for t in expected}
assert found==expected,(found,expected)
assert n('SELECT COUNT(*) FROM study_findings WHERE mapping_status="NOT_ISOLATED"')==61
assert n('SELECT COUNT(*) FROM study_findings WHERE mapping_status="MAPPED"')==781
assert n('SELECT COUNT(*) FROM study_runs WHERE patch_embedded=1')==61
assert n('SELECT COUNT(*) FROM study_runs WHERE raw_scan_embedded=1')==68
assert n('SELECT COUNT(*) FROM study_runs WHERE before_count IS NOT NULL AND after_count IS NOT NULL')==28
assert n('SELECT COUNT(*) FROM study_human_reviews WHERE status="USER_ADJUDICATED"')==41
assert n('SELECT COUNT(*) FROM study_human_reviews WHERE status="ALL_THREE_AGREE_NO_USER_VERDICT"')==8
assert n('SELECT COUNT(*) FROM study_human_reviews WHERE status="USER_DEFERRED"')==1
assert n('SELECT COUNT(*) FROM study_artifacts WHERE storage_status="EXTERNAL_ONLY"')==28
assert n('SELECT COUNT(*) FROM arno_generated_patches WHERE patch_blob IS NOT NULL')==61
assert n('SELECT COUNT(*) FROM arno_experiment_scans WHERE raw_result_blob IS NOT NULL')==68
assert n('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes WHERE patch_zlib IS NOT NULL')==40
assert n('SELECT COUNT(*) FROM arno_rq3_codeql_screen65_original WHERE result_zlib IS NOT NULL')==65
fks={}
for t in expected:
 bad=db.execute('PRAGMA foreign_key_check("'+t+'")').fetchall()
 fks[t]=len(bad)
assert not any(fks.values()),fks
assert n('SELECT COUNT(*) FROM study_findings f WHERE change_key IS NOT NULL AND NOT EXISTS(SELECT 1 FROM study_producing_changes c WHERE c.change_key=f.change_key)')==0
assert n('SELECT COUNT(*) FROM study_human_reviews h WHERE NOT EXISTS(SELECT 1 FROM study_roots r WHERE r.root_id=h.root_id)')==0
report={'status':'BOUNDED_INDEPENDENT_INTEGRITY_GATE_PASS',
'new_database':str(P),'bytes':P.stat().st_size,'row_counts':found,'new_table_fk_errors':fks,
'full_original_master_snapshot_preserved':True,
'raw_patch_bytes_and_scan_bytes_in_same_db':True,
'full_historical_table_by_table_count_validation':'SEPARATE_LONG_RUNNING_AUDIT',
'private_only_public_confidentiality_gate':'REQUIRED',
'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(O/'BOUNDED_INTEGRITY_PASS.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
db.close()
