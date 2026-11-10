#!/usr/bin/env python3
"""Read-only ARNO evidence inventory. Never writes SQLite or exports secrets."""
import hashlib
import json
import os
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime, timezone
R = Path.home() / "research_artifacts"
DB = R / "ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT = R / "mcp_uploads/jobs/arno_master_readonly_audit_20261028/report.json"
out = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "master": {}, "archive_audit": {}, "original_patches": {}, "source_versions": {}, "errors": []}
def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""): h.update(b)
    return h.hexdigest()
def lookup(name):
    p=R / "ARNO_CODEQL_EXPORT_20261019" / name
    d={"exists":p.is_file()}
    if p.is_file():
        d["bytes"]=p.stat().st_size
        if p.stat().st_size < 30000000: d["sha256"]=sha256(p)
        if p.suffix==".zip":
            with zipfile.ZipFile(p) as z:
                n=z.namelist()
                d["members"]=len(n)
                d["matches_08461_O"]=[x for x in n if "08461" in x and "_O" in x][-12:]
                d["matches_15151_O"]=[x for x in n if "15151" in x and "_O" in x][-12:]
                d["example_paths"]=n[:5]
    return d
v=os.statvfs(R)
out["master"]["free_gib"]=round(v.f_bavail*v.f_frsize/(1024**3),3)
out["master"]["db_bytes"]=DB.stat().st_size
con=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=30)
con.execute("PRAGMA query_only=ON")
out["master"]["journal_mode"]=con.execute("PRAGMA journal_mode").fetchone()[0]
tables=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'arno_%'")]
needed=["arno_root_decisions","arno_pc_root_lineage","arno_d7_final_M_roots_233","arno_d7_final_roots_342","arno_new70_final_findings","arno_new70_final_producing_changes","arno_rq2_c6_pairs","arno_rq2_c7_pathways","arno_generated_patches","arno_experiment_runs","arno_experiment_scans","arno_recovered_agent_patch_bytes","arno_seven_final_repair_case_evidence"]
out["master"]["table_counts"]={}
for t in needed:
    out["master"]["table_counts"][t]=con.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] if t in tables else "ABSENT"
out["source_versions"]["c5_c6_original_assets"]=[{"path":str(p),"cohort":c,"role":role,"size":size,"sha256":sha} for p,c,role,size,sha in con.execute("SELECT source_path,cohort,artifact_role,original_bytes,source_sha256 FROM arno_evidence_assets WHERE cohort IN ('C5','C6') ORDER BY cohort,source_path LIMIT 45")]
out["source_versions"]["d7_sources"]=[{"key":k,"sha256":sha,"verification":v} for k,sha,v in con.execute("SELECT source_key,source_sha256,verification FROM arno_sources WHERE source_key LIKE 'D7_%'")]
con.close()
for name in ["02_ALL_GENERATED_PATCHES.zip","03_CODEQL_SARIF_AND_SCANS.zip","04_FUNCTIONAL_TESTS_AND_TRIAGE.zip","07_AGENT_PROMPTS_AND_TRACES.zip"]:
    try: out["archive_audit"][name]=lookup(name)
    except Exception as e: out["errors"].append(name+": "+str(e))
for case in ["08461","15151"]:
    out["original_patches"][case] = {"standalone_patch_candidates_from_zip":{k:v.get("matches_"+case+"_O",[]) for k,v in out["archive_audit"].items()},"original_input_O_packet_exists":(R / ("prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_"+case+"_O.zip")).is_file()}
OUT.parent.mkdir(parents=True,exist_ok=True)
if OUT.exists(): raise SystemExit("Audit file exists: refusing overwrite")
OUT.write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps({"status":"READ_ONLY_PASS","report":str(OUT),"db_bytes":out["master"]["db_bytes"],"free_gib":out["master"]["free_gib"],"table_counts":out["master"]["table_counts"],"patch_status":out["original_patches"],"errors":out["errors"]},indent=2))
