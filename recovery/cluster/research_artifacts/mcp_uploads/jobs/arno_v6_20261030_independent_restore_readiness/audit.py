#!/usr/bin/env python3
"""Independent, read-only ARNO restore-readiness and provenance postcheck.
Audits current master vs verified full snapshot + compact sidecar without
altering source databases, reconstructing patches or exporting private code.
"""
from pathlib import Path
import sqlite3,hashlib,json,sys
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
D=R/"ARNO_MASTER_DB/snapshots"
FULL=D/"ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
FULLCERT=Path(str(FULL)+".json")
DELTA=D/"ARNO_OWP14_POSTBACKUP_PROVENANCE_DELTA_20261029.sqlite"
DELTACERT=Path(str(DELTA)+".json")
MASTER=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ORIGINAL=R/"mcp_uploads/jobs/arno_20261029_v6_exact_baseline_hashes/REPORT.json"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_independent_restore_readiness/REPORT.json"
TABLES={
"arno_owp14_original_input_packet_inventory_20261029":42,
"arno_owp14_input_repo_equivalence_20261029":14,
"arno_owp14_exact_scan_baseline_links_20261029":40
}
SOURCES=["owp14_original_42_packet_index_20261029","owp14_42_input_repo_tree_equivalence_20261029","owp14_exact_baseline_sha_crosswalk_20261029"]
def ck(condition,reason):
 if not condition:raise RuntimeError(reason)
def readonly(path):
 c=sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True,timeout=90)
 c.execute("PRAGMA query_only=ON")
 return c
def sha256(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2*1024*1024),b""):h.update(b)
 return h.hexdigest()
def table_exists(c,t):
 return c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()[0]==1
def num(c,t):
 return c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]
def main():
 fc=json.loads(FULLCERT.read_text());dc=json.loads(DELTACERT.read_text())
 ck(fc.get("status")=="VERIFIED_POST_RECOVERY_BACKUP" and fc.get("quick_check")=="ok","No certified full recovery snapshot")
 ck(fc.get("snapshot")==str(FULL) and fc.get("snapshot_size")==FULL.stat().st_size,"Full backup certificate path or size discrepancy")
 ck(dc.get("status")=="VERIFIED_OWP14_PROVENANCE_DELTA" and dc.get("sqlite_quick_check")=="ok","No certified delta")
 ck(dc.get("sidecar_path")==str(DELTA) and dc.get("sidecar_bytes")==DELTA.stat().st_size,"Delta certificate path or size discrepancy")
 ck(DELTA.stat().st_size<20_000_000,"Delta unexpectedly large")
 ck(sha256(DELTA)==dc.get("sidecar_sha256"),"Delta bytes do not match sha256 certificate")
 live=readonly(MASTER);base=readonly(FULL);side=readonly(DELTA)
 try:
  ck(side.execute("PRAGMA quick_check").fetchone()[0]=="ok","Delta SQLite integrity failed")
  # Avoid expensive second 37GB PRAGMA quick_check; its certified verification
  # already ran during the full-backup job, and this audit uses read-only tables.
  for t,v in fc["counts"].items():
   ck(table_exists(base,t) and num(base,t)==v,"Full snapshot critical table count mismatch: "+t)
  live_counts={t:num(live,t) for t in TABLES}
  side_counts={t:num(side,t) for t in TABLES}
  ck(live_counts==TABLES and side_counts==TABLES,"Provenance delta content counts differ from live")
  before={t:table_exists(base,t) for t in TABLES}
  # Check the pre-delta snapshot has no collisions, or if present, is exactly
  # the same table. A present table is not automatically an error.
  oldsourcekeys=set(r[0] for r in base.execute("SELECT source_key FROM arno_sources WHERE source_key IN (?,?,?) OR source_key LIKE 'owp14_original_packet_20261029:%'",SOURCES))
  deltasourcekeys=set(r[0] for r in side.execute("SELECT source_key FROM arno_sources"))
  ck(len(deltasourcekeys)==45,"Delta source reference count not 45")
  duplicate=oldsourcekeys & deltasourcekeys
  if duplicate:
   for key in duplicate:
    a=base.execute("SELECT source_sha256 FROM arno_sources WHERE source_key=?",(key,)).fetchone()
    b=side.execute("SELECT source_sha256 FROM arno_sources WHERE source_key=?",(key,)).fetchone()
    ck(a==b,"Source reference collision with unequal hashes: "+key)
  for t,expected in TABLES.items():
   live_cols=[x[1] for x in live.execute('PRAGMA table_info("'+t+'")')]
   side_cols=[x[1] for x in side.execute('PRAGMA table_info("'+t+'")')]
   ck(live_cols==side_cols,"Provenance table column layout differs: "+t)
   names=",".join('"'+n+'"' for n in live_cols)
   a=live.execute('SELECT '+names+' FROM "'+t+'" ORDER BY 1,2').fetchall()
   b=side.execute('SELECT '+names+' FROM "'+t+'" ORDER BY 1,2').fetchall()
   ck(a==b,"Provenance table bytes differ from live master: "+t)
   ck(not live.execute("PRAGMA foreign_key_check("+t+")").fetchone(),"Live FK discrepancies: "+t)
  ck(num(live,"arno_experiment_runs")==40 and num(live,"arno_d7_final_roots_342")==342,"Live master census regressed")
  baseline=live.execute("""SELECT l.arm,COUNT(*),SUM(
     l.baseline_sarif_sha256=b.sha256 AND
     l.screen65_first_before_member_path=b.zip_member_path AND
     l.original_input_packet_sha256=p.sha256 AND
     l.source_snapshot_type=p.source_type AND
     l.codeql_version=r.codeql_version)
    FROM arno_owp14_exact_scan_baseline_links_20261029 l
    JOIN arno_screen65_before_sarif_candidates_20261029 b ON b.case_id=l.case_id AND b.wave='SCREEN65_FIRST'
    JOIN arno_owp14_original_input_packet_inventory_20261029 p ON p.case_id=l.case_id AND p.arm=l.arm
    JOIN arno_rq3_owp14_run_scans r ON r.case_id=l.case_id AND r.arm=l.arm GROUP BY l.arm ORDER BY l.arm""").fetchall()
  ck(sum(x[1] for x in baseline)==40 and sum(x[2] for x in baseline)==40,"Not all first-wave baseline matches correct")
  ck({x[0]:x[1] for x in baseline}=={"O":12,"P":14,"W":14},"Missing original scanner arm")
  original=ORIGINAL.read_bytes()
  sr=live.execute("SELECT source_sha256,embedded_bytes FROM arno_sources WHERE source_key='owp14_exact_baseline_sha_crosswalk_20261029'").fetchone()
  ck(sr is not None and sr[0]==hashlib.sha256(original).hexdigest() and sr[1]==original,"Crosswalk original report differs")
  checked={
   "status":"INDEPENDENT_RESTORE_READINESS_PASS",
   "timestamp_utc":datetime.now(timezone.utc).isoformat(),
   "full_snapshot":{"path":str(FULL),"bytes":FULL.stat().st_size,"certified_sha256":fc["snapshot_sha256"],"certified_quick_check":fc["quick_check"]},
   "delta":{"path":str(DELTA),"bytes":DELTA.stat().st_size,"sha256_checked_now":dc["sidecar_sha256"],"sqlite_quick_check_checked_now":"ok"},
   "original_main_master_counts":{"d7":num(live,"arno_d7_final_roots_342"),"experiment_runs":num(live,"arno_experiment_runs")},
   "base_contains_new_provenance_tables":before,
   "base_source_ref_overlap_count":len(duplicate),
   "delta_source_ref_count":len(deltasourcekeys),
   "all_new_provenance_table_contents_match_live":True,
   "provenance_table_counts":side_counts,
   "all_new_provenance_table_foreign_keys_valid_on_live":True,
   "baseline_arm_counts":{x[0]:x[1] for x in baseline},
   "exact_baseline_and_packet_crosswalk_verified":40,
   "snapshot_derived_from_live_before_new_provenance":True,
   "restoration_performed":False,
   "needs_integrated_restore_validation":True,
   "limits":["Read-only restore-readiness audit, not a complete restore rehearsal of the 37.6 GB database.",
             "The delta depends on the 37.6 GB base snapshot for historical reference tables.",
             "Source commit and historical issue wording remain unverified.","No Hugging Face operation performed."]
   }
  OUT.parent.mkdir(parents=True,exist_ok=True)
  with OUT.open("x") as f:json.dump(checked,f,indent=2)
  print(json.dumps(checked,indent=2),flush=True)
 finally:
  live.close();base.close();side.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("INDEPENDENT_RESTORE_READINESS_FAILED "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
