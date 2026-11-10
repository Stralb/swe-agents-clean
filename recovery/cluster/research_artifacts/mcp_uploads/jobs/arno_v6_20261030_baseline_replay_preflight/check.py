#!/usr/bin/env python3
"""Read-only last-mile replay preflight for 37.6GB base snapshot + OWP sidecar.
Checks exact overlapping row bytes, baseline referential targets and collision
safety; never modifies live, base, or delta databases.
"""
from pathlib import Path
from datetime import datetime,timezone
import sqlite3,json,hashlib,sys
R=Path.home()/"research_artifacts"
ROOT=R/"ARNO_MASTER_DB/snapshots"
BASE=ROOT/"ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
SIDE=ROOT/"ARNO_OWP14_POSTBACKUP_PROVENANCE_DELTA_20261029.sqlite"
LIVE=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_baseline_replay_preflight/REPORT.json"
KEY="owp14_exact_baseline_sha_crosswalk_20261029"
TABLES={"arno_owp14_original_input_packet_inventory_20261029":42,
        "arno_owp14_input_repo_equivalence_20261029":14,
        "arno_owp14_exact_scan_baseline_links_20261029":40}
def check(ok,msg):
 if not ok:raise RuntimeError(msg)
def ro(p):
 c=sqlite3.connect("file:"+str(p)+"?mode=ro",uri=True,timeout=90)
 c.execute("PRAGMA query_only=ON")
 return c
def sqlcols(c,t):
 return [r[1] for r in c.execute('PRAGMA table_info("'+t+'")')]
def values(c,t):
 cols=sqlcols(c,t)
 q="SELECT "+",".join('"'+x+'"' for x in cols)+' FROM "'+t+'" ORDER BY 1,2'
 return c.execute(q).fetchall()
def main():
 fullcert=json.loads(Path(str(BASE)+".json").read_text())
 deltacert=json.loads(Path(str(SIDE)+".json").read_text())
 check(fullcert.get("status")=="VERIFIED_POST_RECOVERY_BACKUP" and fullcert.get("quick_check")=="ok","Base uncertified")
 check(deltacert.get("status")=="VERIFIED_OWP14_PROVENANCE_DELTA" and deltacert.get("sqlite_quick_check")=="ok","Delta uncertified")
 for p,key in [(BASE,"snapshot_size"),(SIDE,"sidecar_bytes")]:
  check(p.is_file() and p.stat().st_size==(fullcert if p==BASE else deltacert)[key],"Snapshot size mismatch "+str(p))
 check(SIDE.stat().st_size<2_000_000,"Delta unexpectedly large")
 h=hashlib.sha256(SIDE.read_bytes()).hexdigest()
 check(h==deltacert["sidecar_sha256"],"Delta SHA mismatch")
 base,side,live=[ro(x) for x in (BASE,SIDE,LIVE)]
 try:
  check(base.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(list(TABLES)[2],)).fetchone()[0]==0,"Baseline table unexpectedly exists in base")
  check(side.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(list(TABLES)[2],)).fetchone()[0]==1,"Baseline table not in delta")
  for t in list(TABLES)[:2]:
   check(sqlcols(base,t)==sqlcols(side,t)==sqlcols(live,t),"Common table column mismatch "+t)
   check(values(base,t)==values(side,t)==values(live,t),"Common table rows differ "+t)
  sourcefields=sqlcols(side,"arno_sources")
  check(sourcefields==sqlcols(base,"arno_sources")==sqlcols(live,"arno_sources"),"Original source schema discrepancy")
  seen=set()
  overlap=0
  new=[]
  for row in values(side,"arno_sources"):
   sourcekey=row[sourcefields.index("source_key")]
   check(sourcekey not in seen,"Duplicate key in delta")
   seen.add(sourcekey)
   old=base.execute("SELECT "+",".join('"'+x+'"' for x in sourcefields)+" FROM arno_sources WHERE source_key=?",(sourcekey,)).fetchone()
   if old is None:new.append(sourcekey)
   else:
    check(old==row,"Original source registry conflict "+sourcekey)
    overlap+=1
  check(overlap==44 and new==[KEY],"Unexpected source records to add: "+str(new))
  check(len(seen)==45,"Source count not 45")
  check(len(values(side,list(TABLES)[2]))==40,"Missing 40 delta scan links")
  check(values(side,list(TABLES)[2])==values(live,list(TABLES)[2]),"40 scan links differ in live master")
  # Verify FKs of the delta's new table can be fulfilled in the base before replay.
  q='SELECT case_id,arm,baseline_sarif_sha256,original_input_packet_sha256,screen65_first_before_member_path,codeql_version,source_snapshot_type FROM "arno_owp14_exact_scan_baseline_links_20261029"'
  linked=side.execute(q).fetchall()
  arms={}
  for case,arm,baseline,packet,path,ver,snapshot in linked:
   ref=base.execute("SELECT sha256,zip_member_path FROM arno_screen65_before_sarif_candidates_20261029 WHERE case_id=? AND wave='SCREEN65_FIRST'",(case,)).fetchone()
   scan=base.execute("SELECT codeql_version,source_snapshot_type FROM arno_rq3_owp14_run_scans WHERE case_id=? AND arm=?",(case,arm)).fetchone()
   src=base.execute("SELECT sha256,source_type FROM arno_owp14_original_input_packet_inventory_20261029 WHERE case_id=? AND arm=?",(case,arm)).fetchone()
   check(ref==(baseline,path) and scan==(ver,snapshot) and src==(packet,snapshot),"Base original evidence missing for "+str(case)+":"+arm)
   arms[arm]=arms.get(arm,0)+1
  check(arms=={"O":12,"P":14,"W":14},"Arm counts wrong")
  check(base.execute("SELECT COUNT(*) FROM arno_d7_final_roots_342").fetchone()[0]==342,"D7 source not preserved in base")
  check(base.execute("SELECT COUNT(*) FROM arno_experiment_scans").fetchone()[0]==40,"Scan source not preserved in base")
  check(side.execute("PRAGMA quick_check").fetchone()[0]=="ok","Portable SQLite delta corrupt")
  report={"status":"BASE_PLUS_DELTA_REPLAY_PREFLIGHT_PASS",
    "verified_at_utc":datetime.now(timezone.utc).isoformat(),
    "base_snapshot":str(BASE),"base_snapshot_certified_sha256":fullcert["snapshot_sha256"],
    "delta_snapshot":str(SIDE),"delta_snapshot_sha256_checked":h,
    "base_common_tables_already_present":{k:TABLES[k] for k in list(TABLES)[:2]},
    "identical_source_rows_in_base_and_delta":overlap,
    "missing_source_keys_to_import":new,
    "missing_table_to_import":"arno_owp14_exact_scan_baseline_links_20261029",
    "missing_table_rows":40,"case_count":14,"arm_counts":arms,
    "new_table_FK_targets_present_in_base":True,
    "no_master_or_snapshot_write":True,
    "full_copy_restoration_not_performed":True,
    "proposed_safe_replay":"Copy base SQLite to NEW path; within one transaction insert ONLY missing source key and missing 40-row baseline table from sidecar; verify FKs and SQLite quick_check before certifying.",
    "scientific_limits":["Exact SARIF baseline and packet identities are verified; historical PR commit identity and issue wording remain unverified.",
       "Delta alone is not a full database."] }
  OUT.parent.mkdir(parents=True,exist_ok=True)
  with OUT.open("x") as f:json.dump(report,f,indent=2)
  print(json.dumps(report,indent=2))
 finally:
  base.close();side.close();live.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("BASE_PLUS_DELTA_PREFLIGHT_FAILURE "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
