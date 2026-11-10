#!/usr/bin/env python3
"""Adversarial invariant and source-preservation check of NEW Wits database."""
import sqlite3,json,hashlib,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
DB=O/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
MASTER=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
assert (O/"BACKUP_VERIFICATION.json").exists()
assert (O/"CORE_COUNTS.json").exists()
assert (O/"EVIDENCE_COUNTS.json").exists()
source=sqlite3.connect("file:"+str(MASTER)+"?mode=ro",uri=True)
new=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=240)
def n(db,sql):return db.execute(sql).fetchone()[0]
source_tables=n(source,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
backup_source_tables=n(new,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'study_%'")
assert source_tables==backup_source_tables==127
original_tables=[row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
mismatch=[]
for tab in original_tables:
 a=n(source,'SELECT COUNT(*) FROM "'+tab+'"')
 b=n(new,'SELECT COUNT(*) FROM "'+tab+'"')
 if a!=b:mismatch.append([tab,a,b])
assert not mismatch,mismatch
# Do not claim ability to reproduce experiment from a hash alone: actual blobs must still exist.
for sql,expect in [
 ("SELECT COUNT(*) FROM arno_generated_patches WHERE patch_blob IS NOT NULL",61),
 ("SELECT COUNT(*) FROM arno_experiment_scans WHERE raw_result_blob IS NOT NULL",68),
 ("SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes WHERE patch_zlib IS NOT NULL",40),
 ("SELECT COUNT(*) FROM arno_rq3_owp14_run_scans WHERE original_result_zlib IS NOT NULL",40),
 ("SELECT COUNT(*) FROM arno_rq3_codeql_screen65_original WHERE result_zlib IS NOT NULL",65),
 ("SELECT COUNT(*) FROM arno_recovered_agent_patch_bytes WHERE patch_zlib IS NOT NULL",91),
 ("SELECT COUNT(*) FROM arno_new70_final_findings",237),
 ("SELECT COUNT(*) FROM arno_original_step1_detail",605)]:
 assert n(new,sql)==expect,(sql,n(new,sql),expect)
summary={}
for tab in ["study_cases","study_findings","study_producing_changes","study_classifications","study_roots",
            "study_runs","study_artifacts","study_human_reviews","study_limitations"]:
 summary[tab]=n(new,"SELECT COUNT(*) FROM "+tab)
assert summary=={"study_cases":192,"study_findings":842,"study_producing_changes":455,
"study_classifications":192,"study_roots":342,"study_runs":68,
"study_artifacts":633,"study_human_reviews":50,"study_limitations":12},summary
assert n(new,"SELECT COUNT(*) FROM study_findings WHERE mapping_status='MAPPED'")==781
assert n(new,"SELECT COUNT(*) FROM study_findings WHERE mapping_status='NOT_ISOLATED'")==61
assert n(new,"SELECT COUNT(*) FROM study_findings WHERE change_key IS NOT NULL AND change_key NOT IN (SELECT change_key FROM study_producing_changes)")==0
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE patch_embedded=1")==61
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE raw_scan_embedded=1")==68
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE before_count IS NOT NULL AND after_count IS NOT NULL")==28
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE before_sarif_sha256 IS NOT NULL")==40
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE historical_revision_equivalence='NOT_VERIFIED'")==40
assert n(new,"SELECT COUNT(*) FROM study_runs WHERE experimental_family='RQ3_OWP14_NEW_GENERATION_NONBLIND_20261031'")==2
assert n(new,"SELECT COUNT(*) FROM study_human_reviews WHERE status='USER_ADJUDICATED'")==41
assert n(new,"SELECT COUNT(*) FROM study_human_reviews WHERE status='ALL_THREE_AGREE_NO_USER_VERDICT'")==8
assert n(new,"SELECT COUNT(*) FROM study_human_reviews WHERE status='USER_DEFERRED'")==1
assert n(new,"SELECT COUNT(*) FROM study_classifications WHERE implementation_label IS NULL")==70
# Check all NEW FK declarations, without papering over errors in unchanged archival source tables.
fks=[tuple(x) for x in new.execute("PRAGMA foreign_key_check") if str(x[0]).startswith("study_")]
assert not fks,fks[:20]
# Compact source schema fingerprints, not a claim of whole-file cryptographic identity.
sourceddl=[(x[0],x[1]) for x in source.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name")]
newddl=[(x[0],x[1]) for x in new.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'study_%' ORDER BY name")]
assert sourceddl==newddl,"Historical schema was modified"
source_stats={"bytes":MASTER.stat().st_size,"mtime":MASTER.stat().st_mtime}
assert source_stats["bytes"]==42186481664,"Master size changed, investigate before publishing"
status={
 "status":"RESTRICTED_NEW_UNIFIED_DB_VERIFIED_NOT_PUBLIC",
 "source_master_unchanged":True,
 "source_tables":source_tables,
 "source_table_count_mismatches":mismatch,
 "new_db_tables":n(new,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"),
 "new_normalized_tables":summary,
 "full_original_raw_bytes_preserved":True,
 "original_master_size_bytes":source_stats["bytes"],
 "new_database_size_bytes":DB.stat().st_size,
 "fk_errors_new_layer":len(fks),
 "source_ddl_unchanged":True,
 "review_status":"SINGLE_RESEARCHER_POSTHOC_AI_ASSISTED_NOT_INDEPENDENT",
 "not_isolated_findings":61,
 "historical_baseline_revision_equivalence":"NOT_VERIFIED",
 "public_release_status":"BLOCKED_ON_RAW_ARTIFACT_CONFIDENTIALITY_LICENSE_SCREEN",
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "database_path":str(DB)}
(O/"UNIFIED_VALIDATION.json").write_text(json.dumps(status,indent=2)+"\n")
(O/"REVIEWER_SQL_QUERIES.sql").write_text(
"""-- The new DB is RESTRICTED; raw source evidence includes uncontrolled third-party code.
SELECT collection_phase,COUNT(*) cases FROM study_cases GROUP BY collection_phase;
SELECT count(*) findings FROM study_findings;
SELECT mapping_status,count(*) n FROM study_findings GROUP BY mapping_status;
SELECT attribution,count(*) n FROM study_producing_changes GROUP BY attribution;
SELECT experimental_family,count(*) n,SUM(patch_embedded) patches,SUM(raw_scan_embedded) raw_scans FROM study_runs GROUP BY experimental_family;
SELECT * FROM study_paper_findings WHERE case_id=3429;
SELECT * FROM study_paper_human_reviews;
SELECT * FROM study_limitations;
""")
source.close();new.close()
print(json.dumps(status,indent=2),flush=True)
