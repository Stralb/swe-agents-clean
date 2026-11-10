#!/usr/bin/env python3
"""Online consistent SQLite backup of original Wits master to NEW path only."""
import sqlite3,hashlib,os,time,json
from pathlib import Path
root=Path.home()/"research_artifacts"
src=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
out=root/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
out.mkdir(parents=True,exist_ok=True)
dst=out/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
tmp=out/"ARNO_UNIFIED_FULL_EVIDENCE_DB.building.sqlite"
assert src.is_file() and not dst.exists() and not tmp.exists()
a=sqlite3.connect("file:"+str(src)+"?mode=ro",uri=True,timeout=240)
a.execute("PRAGMA query_only=ON")
b=sqlite3.connect(str(tmp),timeout=240)
start=time.time()
def progress(status,remaining,total):
    if total and remaining%50000<4096:
        print(json.dumps({"backup_remaining_pages":remaining,"backup_total_pages":total,"elapsed_s":round(time.time()-start)}),flush=True)
a.backup(b,pages=4096,progress=progress,sleep=0.03)
b.commit()
checks={"source_bytes":src.stat().st_size,"backup_bytes":tmp.stat().st_size,
"source_tables":a.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
"backup_tables":b.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]}
for t in ["cases","arno_classifications","arno_original_step1_detail","arno_original_step2_detail",
          "arno_new70_final_findings","arno_new70_final_finding_maps","arno_new70_final_producing_changes",
          "arno_experiment_runs","arno_generated_patches","arno_experiment_scans","arno_chat_evidence_objects",
          "arno_d7_final_roots_342","arno_recovered_agent_patch_bytes","arno_archive_vault_members"]:
  qa=a.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]
  qb=b.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]
  assert qa==qb,(t,qa,qb)
  checks[t]=qb
assert checks["source_tables"]==checks["backup_tables"]
assert checks["source_tables"]>=127
assert checks["arno_original_step1_detail"]==605
assert checks["arno_new70_final_findings"]==237
b.close();a.close()
os.replace(tmp,dst)
report={"status":"SOURCE_SNAPSHOT_COPY_COMPLETE_VERIFIED","source_modified":False,
"source":str(src),"new_database":str(dst),"clone_bytes":dst.stat().st_size,
"elapsed_seconds":round(time.time()-start,1),"checks":checks}
(out/"BACKUP_VERIFICATION.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
