#!/usr/bin/env python3
"""Post-import, strictly read-only, independent verification of OWP14 normalization."""
import sqlite3,json,hashlib,os,sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_owp40_postcheck_20261028/POSTCHECK.json"
def sha(b):return hashlib.sha256(b).hexdigest()
def expect(cond,msg):
 if not cond:raise RuntimeError(msg)
cn=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=30)
cn.execute("PRAGMA query_only=ON")
src=cn.execute("""SELECT case_id,arm,patch_sha256,codeql_version,historical_target_rule,scan_state
 FROM arno_rq3_owp14_run_scans ORDER BY case_id,arm""").fetchall()
expect(len(src)==40,"source row count")
stats=Counter()
for case,arm,patch_sha,ver,rule,scan_state in src:
 tok=f"OWP14_CASE{case:05d}_{arm}"
 r=cn.execute("SELECT case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status FROM arno_experiment_runs WHERE run_id=?",(tok,)).fetchone()
 expect(r is not None and r[0]==case and r[1] is None and r[2]=="RQ3_OWP14_ARCHIVED_SCAN_ARM" and r[3]==arm and r[4] is None,(tok,"run metadata mismatch"))
 expect(r[6]=="ORIGINAL_ARCHIVED_PATCH_AND_SCANNER_RESULT_NOT_REEXECUTED",(tok,"false execution status"))
 meta=json.loads(r[5])
 p=cn.execute("SELECT content_sha256,patch_blob,authenticity_status FROM arno_generated_patches WHERE patch_id=? AND run_id=?",(tok+"_PATCH",tok)).fetchone()
 expect(p is not None and p[0]==patch_sha and sha(p[1])==patch_sha and p[2]=="ARCHIVED_PATCH_SHA256_VERIFIED_AGENT_ORIGIN_UNVERIFIED",(tok,"patch mismatch"))
 s=cn.execute("SELECT scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified FROM arno_experiment_scans WHERE scan_id=? AND run_id=?",(tok+"_CODEQL_AFTER",tok)).fetchone()
 expect(s is not None and s[0]=="CodeQL" and s[1]==ver and s[2]==rule and s[5]==0,(tok,"scan metadata mismatch"))
 expect(sha(s[3])==meta["sarif_sha256"],(tok,"SARIF hash mismatch"))
 expect(s[4]==r[5],(tok,"metadata not linked"))
 expect(scan_state=="SCAN_COMPLETE",(tok,"archived scan incomplete"))
 stats[arm]+=1
for table,key,suffix in [("arno_experiment_runs","run_id",""),("arno_generated_patches","patch_id","_PATCH"),("arno_experiment_scans","scan_id","_CODEQL_AFTER")]:
 ids=cn.execute("SELECT "+key+" FROM "+table+" WHERE "+key+" LIKE 'OWP14_CASE%'").fetchall()
 expect(len(ids)==40,(table,"row count",len(ids)))
 expect(not cn.execute("PRAGMA foreign_key_check("+table+")").fetchone(),(table,"FK violation"))
expect(stats=={"O":12,"W":14,"P":14},("arm counts",stats))
out={"status":"INDEPENDENT_POSTCHECK_PASS","utc":datetime.now(timezone.utc).isoformat(),"records":40,"arms":dict(stats),"normalized_runs":40,"normalized_patches":40,"normalized_scans":40,"patch_hashes_matched":40,"sarif_hashes_matched":40,"foreign_keys":"PASS","execution_reproduced":False,"agent_prompt_recovered":False,"huggingface_updated":False,"database":str(DB)}
cn.close()
OUT.parent.mkdir(parents=True,exist_ok=True)
if OUT.exists():raise RuntimeError("Report exists; refusing overwrite")
OUT.write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
