#!/usr/bin/env python3
"""Independent source count, referential, byte hash, and per-run deep-patch validation."""
import sqlite3,hashlib,json,datetime,collections
from pathlib import Path
root=Path.home()/"research_artifacts"
out=root/"mcp_uploads/jobs/arno_patch_reconciliation_v2/output"
old=root/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
target=out/"ARNO_UNIFIED_EVIDENCE_WITH_DEEP_PATCHES_V2.sqlite"
assert (out/"SNAPSHOT_VERIFICATION.json").exists() and target.exists()
a=sqlite3.connect("file:"+str(old)+"?mode=ro",uri=True,timeout=120)
b=sqlite3.connect("file:"+str(target)+"?mode=ro",uri=True,timeout=120)
def n(c,q):return c.execute(q).fetchone()[0]
assert n(a,"SELECT COUNT(*) FROM study_runs")==68
original_tables=[(x[0],x[1]) for x in a.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for t,ddl in original_tables:
 row=b.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()
 assert row and row[0]==ddl,("MODIFIED_ORIGINAL_SCHEMA",t)
 nsrc=n(a,'SELECT COUNT(*) FROM "'+t+'"')
 ndst=n(b,'SELECT COUNT(*) FROM "'+t+'"')
 assert nsrc==ndst,("ORIGINAL_ROW_DIFFERENCE",t,nsrc,ndst)
checks={
 "source_user_tables_identical":len(original_tables),
 "source_original_runs":n(b,"SELECT COUNT(*) FROM study_runs"),
 "new_deep_runs":n(b,"SELECT COUNT(*) FROM study_deep_runs"),
 "new_total_view_runs":n(b,"SELECT COUNT(*) FROM study_all_experimental_runs"),
 "rpl7_inputs":n(b,"SELECT COUNT(*) FROM study_deep_input_packages"),
 "rpl7_baselines":n(b,"SELECT COUNT(*) FROM study_deep_baseline"),
 "pilot_inputs":n(b,"SELECT COUNT(*) FROM study_deep_pilot_inputs"),
 "vault_patch_members":n(b,"SELECT COUNT(*) FROM study_deep_vault_patch_index"),
 "vault_only":n(b,"SELECT COUNT(*) FROM study_deep_vault_patch_index WHERE matched_in_previous_master=0"),
 "deep_patch_bytes":n(b,"SELECT COUNT(*) FROM study_deep_evidence WHERE role='patch'"),
 "deep_after_sarifs":n(b,"SELECT COUNT(*) FROM study_deep_evidence WHERE role='after_sarif'"),
 "deep_receipts":n(b,"SELECT COUNT(*) FROM study_deep_evidence WHERE role='receipt'"),
 "deep_scan_results":n(b,"SELECT COUNT(*) FROM study_deep_evidence WHERE role='scan_result'"),
 "prospective_risks":n(b,"SELECT COUNT(*) FROM study_deep_evidence WHERE role='prospective_risks'"),
 "rpl7_p2_p3":n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE cohort_name='RPL7_RETROSPECTIVE_ORACLE'"),
 "AC6_pilots":n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE cohort_name='AC6_EXPLORATORY_NONRANDOMIZED'"),
 "rpl7_P1_existing":n(b,"SELECT COUNT(*) FROM study_deep_input_packages i JOIN study_runs r ON r.run_id=i.run_id WHERE i.condition='P1'"),
}
expected={"source_original_runs":68,"new_deep_runs":26,"new_total_view_runs":94,
"rpl7_inputs":21,"rpl7_baselines":7,"pilot_inputs":3,
"vault_patch_members":255,"vault_only":150,"deep_patch_bytes":33,"deep_after_sarifs":33,
"deep_receipts":33,"deep_scan_results":33,"rpl7_p2_p3":14,"AC6_pilots":12,"rpl7_P1_existing":7}
for x,v in expected.items():assert checks[x]==v,(x,checks[x],v)
assert n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE condition='P2'")==7
assert n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE condition='P3'")==7
assert n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE condition='MECHANISM'")==6
assert n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE condition='PROSPECTIVE_BUILD'")==6
assert n(b,"SELECT COUNT(*) FROM study_deep_runs WHERE functional_status!='NOT_TESTED'")==0
assert n(b,"SELECT COUNT(*) FROM study_all_experimental_runs WHERE run_id NOT IN (SELECT run_id FROM study_runs UNION SELECT run_id FROM study_deep_runs)")==0
for table in ["study_deep_runs","study_deep_input_packages","study_deep_baseline","study_deep_pilot_inputs","study_deep_vault_patch_index"]:
 assert not b.execute('PRAGMA foreign_key_check("'+table+'")').fetchall(),table
# Verify the actual SQLite BLOB bytes, not only submitted strings.
byrun=collections.defaultdict(dict)
total=0
for rid,role,digest,blob in b.execute("SELECT run_id,role,content_sha256,raw_content FROM study_deep_evidence"):
 assert hashlib.sha256(blob).hexdigest()==digest,(rid,role)
 byrun[rid][role]=digest
 total+=1
checks["verified_artifact_blob_hashes"]=total
for rid,patchsha,scan_sha,src in b.execute("SELECT run_id,patch_sha256,after_sarif_sha256,source_kind FROM study_deep_runs"):
 assert byrun[rid]["patch"]==patchsha
 assert byrun[rid]["after_sarif"]==scan_sha
 assert {"patch","receipt","after_sarif","scan_result"}.issubset(byrun[rid]),rid
assert len(byrun)==33
for rid,zip_digest,raw,prompt_sha,prompt in b.execute("SELECT run_id,input_sha256,input_raw_zip,prompt_sha256,original_prompt FROM study_deep_input_packages"):
 assert hashlib.sha256(raw).hexdigest()==zip_digest,rid
 assert hashlib.sha256(prompt).hexdigest()==prompt_sha,rid
for cid,h,data in b.execute("SELECT case_id,baseline_sarif_sha256,raw_sarif FROM study_deep_baseline"):
 assert hashlib.sha256(data).hexdigest()==h,cid
for c,h,raw,ph,prompt in b.execute("SELECT pilot_condition,original_zip_sha256,original_zip,prompt_sha256,prompt FROM study_deep_pilot_inputs"):
 assert hashlib.sha256(raw).hexdigest()==h,c
 assert hashlib.sha256(prompt).hexdigest()==ph,c
assert n(b,"SELECT COUNT(*) FROM study_deep_vault_patch_index x WHERE NOT EXISTS(SELECT 1 FROM arno_archive_vault_objects a WHERE a.object_key=x.source_vault_object_key)")==0
# Historic run summaries recheck, not changing paper table denominators:
assert n(b,"SELECT COUNT(*) FROM study_cases")==192
assert n(b,"SELECT COUNT(*) FROM study_findings")==842
assert n(b,"SELECT COUNT(*) FROM study_producing_changes")==455
assert n(b,"SELECT COUNT(*) FROM study_human_full_records")==50
report={"status":"DEEP_PATCH_INTEGRATION_FULL_VALIDATION_PASS","validation_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"source_unified_database":str(old),"new_database":str(target),
"original_source_db_unchanged":True,"original_source_user_table_schema_and_counts_preserved":True,
"verified_checks":checks,"new_database_bytes":target.stat().st_size,
"limitations":["Source ZIP snapshots include sanitized and sometimes filtered provisional repos",
"Functional correctness was not tested for these deep patch experiments",
"B blind-review case22223 preserved as input only, not fabricated as completed treatment",
"AC arms are non-randomized exploratory pilots, not equivalents of P1/P2/P3",
"Vault per-member hashes imported from preserved manifest, not independently extracted and rehashed",
"Original raw evidence remains restricted pending privacy and third-party license review"]}
(out/"FINAL_INTEGRATION_VALIDATION.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"REVIEWER_EXPANDED_SQL.sql").write_text("""-- Run read-only on V2 database.
SELECT registration_source,experiment_family,condition,COUNT(*) runs FROM study_all_experimental_runs
 GROUP BY registration_source,experiment_family,condition;
SELECT condition,COUNT(*) runs,SUM(new_warnings) new_scanner_alerts
 FROM study_deep_runs WHERE cohort_name='RPL7_RETROSPECTIVE_ORACLE' GROUP BY condition;
SELECT condition,COUNT(*) runs,SUM(new_warnings) new_scanner_alerts
 FROM study_deep_runs WHERE cohort_name='AC6_EXPLORATORY_NONRANDOMIZED' GROUP BY condition;
SELECT COUNT(*) FROM study_deep_input_packages;
SELECT COUNT(*) FROM study_deep_vault_patch_index;
SELECT count(*) FROM study_deep_evidence WHERE role IN ('patch','after_sarif');
SELECT pilot_condition,output_generation_status FROM study_deep_pilot_inputs;
-- Warning counts are not exploitability or functional correctness measures.
""")
print(json.dumps({"status":report["status"],"checks":checks,"bytes":report["new_database_bytes"]},indent=2),flush=True)
a.close();b.close()
