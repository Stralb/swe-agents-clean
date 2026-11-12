#!/usr/bin/env python3
"""Read-only terminal audit of D7 + OWP40 + NEW70 source-byte integration."""
from pathlib import Path
import sqlite3,json,hashlib,sys
from datetime import datetime,timezone
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
snap=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_PRE_OCT28_RQ3_NORMALIZATION.sqlite"
src=R/"mcp_uploads/arno_master_20261028/D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv"
out=R/"mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/RESULT.json"
def check(cond,msg):
 if not cond:raise RuntimeError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
ck=json.loads(Path(str(snap)+".json").read_text())
check(ck.get("status")=="VERIFIED" and ck.get("quick_check")=="ok" and snap.exists(),"Backup not independently certified")
import_report=json.loads((R/"mcp_uploads/jobs/arno_oct28_owp40_normalize/IMPORT_REPORT.json").read_text())
owp_check=json.loads((R/"mcp_uploads/jobs/arno_owp40_postcheck_20261028/POSTCHECK.json").read_text())
new70_report=json.loads((R/"mcp_uploads/jobs/arno_oct28_new70_orig_embed/IMPORT_REPORT.json").read_text())
d7_report=json.loads((R/"mcp_uploads/jobs/arno_20261029_d7_verify/RESULT.json").read_text())
check(import_report["status"]=="IMPORT_COMPLETE","OWP import incomplete")
check(owp_check["status"]=="INDEPENDENT_POSTCHECK_PASS","OWP postcheck incomplete")
check(new70_report["status"]=="NEW70_ORIGINALS_EMBEDDED_AND_VERIFIED","NEW70 source embed incomplete")
check(d7_report["status"]=="POSTCHECK_PASS","D7 postcheck incomplete")
c=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=40)
c.execute("PRAGMA query_only=ON")
def count(t):return c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
required={"arno_root_decisions":342,"arno_pc_root_lineage":455,"arno_d7_final_M_roots_233":233,
 "arno_d7_final_roots_342":342,"arno_experiment_runs":40,"arno_generated_patches":40,
 "arno_experiment_scans":40,"arno_new70_final_findings":237,
 "arno_new70_final_producing_changes":133,"arno_new70_final_unresolved":61,
 "arno_rq3_owp14_run_scans":40}
counts={t:count(t) for t in required}
check(counts==required,"Master row count mismatch: "+repr(counts))
route=dict(c.execute("SELECT final_route,COUNT(*) FROM arno_d7_final_roots_342 GROUP BY final_route"))
check(route=={"M":233,"H":6,"T":103},"D7 route census mismatch")
original=src.read_bytes()
check(sha(original)=="be316e7eb5708d4cf5ac71baafaf82f84fbe15fbb44deb651ac76712d24083b4","D7 source SHA")
a=c.execute("SELECT embedded_bytes,source_sha256 FROM arno_sources WHERE source_key='d7_final_342_user_csv_be316e7e_20261028'").fetchone()
check(a is not None and a[0]==original and a[1]==sha(original),"D7 source embedding changed")
original_sources={}
for name in ["Step1_NEW70_FINAL.zip","NEW70_Phase6_Step2_Mapping_FINAL_v1.0.zip","NEW70_Phase6_Producing_Changes_FINAL_v1.0.csv"]:
 k="new70_original_oct28:"+name
 rec=c.execute("SELECT embedded_bytes,source_sha256 FROM arno_sources WHERE source_key=?",(k,)).fetchone()
 check(rec is not None and sha(rec[0])==rec[1],"NEW70 source byte mismatch "+name)
 original_sources[name]=rec[1]
for table in ("arno_d7_final_roots_342","arno_experiment_runs","arno_generated_patches","arno_experiment_scans"):
 check(c.execute("PRAGMA foreign_key_check("+table+")").fetchone() is None,"FK discrepancy "+table)
c.close()
result={"status":"MASTER_RECOVERY_VERIFIED","timestamp_utc":datetime.now(timezone.utc).isoformat(),
 "database":str(DB),"snapshot_sha256":ck["sha256"],
 "d7_source_sha256":sha(original),"row_counts":counts,"d7_routes":route,
 "new70_original_file_sha256":original_sources,"original_evidence_sha256_verified":True,
 "normalized_rq3_scans_are_archived_not_reexecuted":True,
 "no_claim_of_functional_equivalence_or_confirmed_vulnerability":True,
 "huggingface_updated_by_this_pipeline":False}
out.parent.mkdir(parents=True,exist_ok=True)
with out.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
