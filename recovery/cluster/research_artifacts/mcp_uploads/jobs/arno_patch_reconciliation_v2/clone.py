#!/usr/bin/env python3
"""Safe online backup: new file only, verified source unchanged."""
import sqlite3,json,os,time
from pathlib import Path
root=Path.home()/"research_artifacts"
src=root/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
out=root/"mcp_uploads/jobs/arno_patch_reconciliation_v2/output";out.mkdir(parents=True,exist_ok=True)
dst=out/"ARNO_UNIFIED_EVIDENCE_WITH_DEEP_PATCHES_V2.sqlite"
temp=out/"ARNO_UNIFIED_EVIDENCE_WITH_DEEP_PATCHES_V2.building.sqlite"
assert (root/"mcp_uploads/jobs/arno_patch_reconciliation_v2/PREFLIGHT_REPORT.json").is_file()
assert src.is_file() and not dst.exists() and not temp.exists()
a=sqlite3.connect("file:"+str(src)+"?mode=ro",uri=True,timeout=240)
a.execute("PRAGMA query_only=ON")
b=sqlite3.connect(str(temp),timeout=240)
t=time.monotonic()
a.backup(b,pages=8192,sleep=.025)
b.commit()
tables=["cases","study_cases","study_findings","study_producing_changes","study_runs","study_artifacts",
"study_human_full_records","study_human_full_evidence","arno_archive_vault_members","arno_archive_vault_chunks"]
counts={}
for tab in tables:
 x=a.execute('SELECT COUNT(*) FROM "'+tab+'"').fetchone()[0]
 y=b.execute('SELECT COUNT(*) FROM "'+tab+'"').fetchone()[0]
 assert x==y,(tab,x,y)
 counts[tab]=x
assert a.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()==b.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
b.close();a.close()
assert temp.stat().st_size==src.stat().st_size
os.replace(temp,dst)
report={"status":"NEW_DATABASE_SNAPSHOT_VERIFIED","source":str(src),"new_database":str(dst),"source_changed":False,
"snapshot_bytes":dst.stat().st_size,"old_table_row_counts":counts,"elapsed_seconds":round(time.monotonic()-t,2)}
(out/"SNAPSHOT_VERIFICATION.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
