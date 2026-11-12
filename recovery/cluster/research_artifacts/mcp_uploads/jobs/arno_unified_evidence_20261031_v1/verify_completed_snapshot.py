#!/usr/bin/env python3
"""Validate fully copied SQLite snapshot after verifier off-by-one; no recopy and no source write."""
import sqlite3,os,json,datetime
from pathlib import Path
root=Path.home()/"research_artifacts"
src=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
out=root/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
tmp=out/"ARNO_UNIFIED_FULL_EVIDENCE_DB.building.sqlite"
dst=out/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
assert tmp.is_file() and not dst.exists()
a=sqlite3.connect("file:"+str(src)+"?mode=ro",uri=True,timeout=180)
b=sqlite3.connect("file:"+str(tmp)+"?mode=ro",uri=True,timeout=180)
a.execute("PRAGMA query_only=ON");b.execute("PRAGMA query_only=ON")
sql="SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
tables_source=a.execute(sql).fetchall()
tables_copy=b.execute(sql).fetchall()
assert tables_source==tables_copy,("SCHEMA_DIFFERENCE",len(tables_source),len(tables_copy))
user_tables=[x for x in tables_source if not x[0].startswith("sqlite_")]
assert len(tables_source)==127 and len(user_tables)==126
counts={}
for t in ["cases","arno_classifications","arno_original_step1_detail","arno_original_step2_detail",
"arno_new70_final_findings","arno_new70_final_finding_maps","arno_new70_final_producing_changes",
"arno_experiment_runs","arno_generated_patches","arno_experiment_scans","arno_chat_evidence_objects",
"arno_d7_final_roots_342","arno_recovered_agent_patch_bytes","arno_archive_vault_members"]:
 n1=a.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]
 n2=b.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]
 assert n1==n2,(t,n1,n2)
 counts[t]=n2
assert src.stat().st_size==tmp.stat().st_size==42186481664
a.close();b.close()
os.replace(tmp,dst)
report={"status":"VERIFIED_FULL_MASTER_SNAPSHOT_CREATED","source_modified":False,
"source":str(src),"destination":str(dst),"bytes":dst.stat().st_size,
"all_tables_including_internal":127,"user_tables":126,
"snapshot_consistent_backup_completed":True,
"source_schema_exact_match":True,
"source_record_counts_checked":counts,
"original_assertion_issue":"Expected 127 non-sqlite internal tables, actual 126; fixed without re-copy",
"time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out/"BACKUP_VERIFICATION.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
