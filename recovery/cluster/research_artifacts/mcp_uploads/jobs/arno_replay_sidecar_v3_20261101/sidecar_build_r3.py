#!/usr/bin/env python3
"""ARNO supplementary replay sidecar: independent, append-only, original v1 read-only.
Requires the already-extracted verified v2 integration kit on the Wits cluster.
"""
import json, os, sqlite3, sys, time, zlib
from pathlib import Path
from collections import Counter

ROOT=Path.home()/"research_artifacts"
J=ROOT/"mcp_uploads/jobs"
KIT=J/"arno_v2_import_20261101_review/extracted/ARNO_EVIDENCE_V2_INTEGRATION_KIT_20261101"
sys.path.insert(0,str(KIT))
from wits_integrate_v2 import load_preflight, require, digest, SOURCE_DB

OUTPUT=J/"arno_replay_sidecar_v3_20261101/output_r3"
DEST=OUTPUT/"ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite"
PART=OUTPUT/"ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite.partial"
REPORT=OUTPUT/"ARNO_REPLAY_SIDECAR_v3_QA.json"
TABLES={"study_runs":"run_id","study_artifacts":"artifact_id",
        "arno_experiment_runs":"run_id","arno_generated_patches":"patch_id",
        "arno_experiment_scans":"scan_id"}

def sidecar_schema(db):
 for table,pk in TABLES.items():
  db.execute("CREATE TABLE "+table+"_overlay AS SELECT * FROM frozen."+table+" WHERE 0")
  db.execute("CREATE UNIQUE INDEX ix_"+table+"_overlay ON "+table+"_overlay("+pk+")")
 db.executescript("""
 CREATE TABLE arno_v3_run_evidence(
  run_id TEXT PRIMARY KEY,case_id INTEGER,cohort TEXT,arm TEXT,source_status TEXT,
  source_tree_sha256 TEXT,input_zip_sha256 TEXT,patch_sha256 TEXT,
  before_sarif_sha256 TEXT,after_sarif_sha256 TEXT,before_count INTEGER,
  after_count INTEGER,introduced_count INTEGER,receipt_status TEXT,
  generation_status TEXT,functional_status TEXT,ingested_in_overlay INTEGER);
 CREATE TABLE arno_v3_asset_bytes(
  run_id TEXT NOT NULL,role TEXT NOT NULL,source_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,zlib_blob BLOB NOT NULL,
  PRIMARY KEY(run_id,role));
 CREATE TABLE arno_v3_archive_crosswalk(
  archive_name TEXT,member_path TEXT,case_id TEXT,
  patch_sha256 TEXT,original_bytes INTEGER,indexed_in_master INTEGER,
  matched_master_tables TEXT,byte_status TEXT,
  PRIMARY KEY(archive_name,member_path));
 CREATE TABLE arno_v3_repair_bytes(
  case_id INTEGER PRIMARY KEY,patch_sha256 TEXT,original_bytes INTEGER,
  patch_zlib BLOB NOT NULL,source_table TEXT,verification TEXT);
 CREATE TABLE arno_v3_gap_ledger(
  gap_id TEXT PRIMARY KEY,cohort TEXT,run_id TEXT,case_id INTEGER,
  missing_item TEXT,status TEXT);
 CREATE TABLE arno_v3_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 """)

def insert_item(db,item,exists):
 run=item["run"];case=item["case"];new=not exists
 db.execute("INSERT INTO arno_v3_run_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
  run,case,item["cohort"],item["arm"],item["source"],item["tree_sha"],
  item["source_zip_sha"],item["patch_sha"],item["before_sha"],item["after_sha"],
  item["baseline"],item["after"],item["new"],item["receipt_status"],
  item["agent_status"],item["functional"],int(new)))
 for role,raw,source in item["assets"]:
  h=digest(raw)
  db.execute("INSERT INTO arno_v3_asset_bytes VALUES(?,?,?,?,?,?)",
             (run,role,source,h,len(raw),sqlite3.Binary(zlib.compress(raw,6))))
  db.execute("""INSERT INTO study_artifacts_overlay VALUES(?,?,?,?,?,?,?,?,?)""",(
   "V3:"+run+":"+role,case,run,role,"arno_v3_asset_bytes",run+"/"+role,
   h,"SIDECAR_ZLIB_SHA_VERIFIED",len(raw)))
 if not new:
  return
 p=next(raw for role,raw,loc in item["assets"] if role=="PATCH")
 sarif=next(raw for role,raw,loc in item["assets"] if role=="CODEQL_AFTER_SARIF")
 fam="OCT2026_NEW_P123" if item["cohort"].endswith("RETROSPECTIVE") else "OCT2026_AC_EXPLORATORY"
 treatment=("P123_" if fam=="OCT2026_NEW_P123" else "AC_")+item["arm"]
 db.execute("INSERT INTO arno_experiment_runs_overlay VALUES(?,?,?,?,?,?,?,?)",(
  run,case,None,fam,treatment,None,
  json.dumps({"sidecar_version":"v3","cohort":item["cohort"],
              "agent_origin_attested":False,"functionality_tested":False}),
  "CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED"))
 pid=run+"::PATCH";sid=run+"::CODEQL"
 db.execute("INSERT INTO arno_generated_patches_overlay VALUES(?,?,?,?,?,?,?)",(
  pid,run,item["patch_sha"],sqlite3.Binary(p),None,
  "RETURNED_PATCH_SHA_VERIFIED_GENERATOR_NOT_ATTESTED",
  "Static analyzer alerts are not confirmed vulnerabilities"))
 db.execute("INSERT INTO arno_experiment_scans_overlay VALUES(?,?,?,?,?,?,?,?)",(
  sid,run,"CodeQL",None,None,sqlite3.Binary(sarif),
  json.dumps({"baseline":item["baseline"],"after":item["after"],
              "introduced":item["new"],"before_sha":item["before_sha"],
              "after_sha":item["after_sha"]}),1))
 db.execute("INSERT INTO study_runs_overlay VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
  run,case,fam,treatment,"CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED",
  item["source"],pid,item["patch_sha"],1,sid,1,1,item["baseline"],item["after"],
  item["new"],None,item["before_sha"],item["after_sha"],"NOT_ATTESTED",
  item["functional"],"RETURNED_PATCH_SHA_VERIFIED_GENERATOR_NOT_ATTESTED",
  "arno_generated_patches_overlay","arno_experiment_scans_overlay",
  "arno_v3_run_evidence"))

def copy_verified_index(db):
 rows=db.execute("""SELECT archive_name,member_path,case_id,sha256,original_bytes,
 indexed_in_master,matched_master_tables FROM frozen.arno_archive_vault_members
 WHERE role='PATCH'""").fetchall()
 require(len(rows),255,"archive members")
 for a,m,c,h,n,known,t in rows:
  db.execute("INSERT INTO arno_v3_archive_crosswalk VALUES(?,?,?,?,?,?,?,?)",(
   a,m,c,h,n,known,t,
   "SOURCE_MASTER_MATCH_MEMBER_NOT_REEXTRACTED" if known else
   "ARCHIVE_ONLY_MEMBER_BYTES_NOT_REEXTRACTED"))
 require(sum(r[5]==0 for r in rows),150,"unmatched archive-only")
 repairs=db.execute("""SELECT case_id,final_patch_sha256,final_patch_zlib
 FROM frozen.arno_seven_final_repair_case_evidence""").fetchall()
 require(len(repairs),7,"posthoc repairs")
 for c,h,compressed in repairs:
  b=zlib.decompress(compressed)
  require(digest(b),h,"final repair "+str(c))
  db.execute("INSERT INTO arno_v3_repair_bytes VALUES(?,?,?,?,?,?)",(
   c,h,len(b),sqlite3.Binary(compressed),
   "arno_seven_final_repair_case_evidence","ZLIB_SHA256_VERIFIED"))
 for arm in ("A","B","C"):
  db.execute("INSERT INTO arno_v3_gap_ledger VALUES(?,?,?,?,?,?)",(
   "22223_"+arm,"22223_THREE_PILOT_INPUTS",None,22223,
   "unambiguous per-pilot output patch/scan linkage","PENDING"))
 for run,case in db.execute("""SELECT run_id,case_id FROM arno_v3_run_evidence
 WHERE cohort='OCT2026_AC_SIX_CASE_EXPLORATORY'""").fetchall():
  db.execute("INSERT INTO arno_v3_gap_ledger VALUES(?,?,?,?,?,?)",(
   "AC_PROMPT_"+run,"AC_EXPLORATORY",run,case,
   "original exact prompt-to-run pairing","PENDING"))
 db.execute("INSERT INTO arno_v3_gap_ledger VALUES(?,?,?,?,?,?)",(
  "ARCHIVE_ONLY_150","HISTORICAL_ARCHIVES",None,None,
  "individual archived patch member bytes, 150 indexed entries","PENDING"))
 
def verify(db):
 reqs=[("SELECT count(*) FROM frozen.study_runs",68),
       ("SELECT count(*) FROM study_runs_overlay",26),
       ("SELECT count(*) FROM arno_v3_run_evidence",33),
       ("SELECT count(*) FROM arno_v3_asset_bytes",207),
       ("SELECT count(*) FROM arno_v3_archive_crosswalk",255),
       ("SELECT count(*) FROM arno_v3_archive_crosswalk WHERE indexed_in_master=0",150),
       ("SELECT count(*) FROM arno_v3_repair_bytes",7),
       ("SELECT count(*) FROM arno_v3_gap_ledger",16),
       ("SELECT count(*) FROM frozen.study_runs s JOIN study_runs_overlay x ON s.run_id=x.run_id",0)]
 for sql,n in reqs:
  got=db.execute(sql).fetchone()[0];require(got,n,sql)
 require(db.execute("SELECT count(*) FROM frozen.study_runs").fetchone()[0]+
         db.execute("SELECT count(*) FROM study_runs_overlay").fetchone()[0],94,
         "virtual consolidated study run count")
 for arm,n in (("P1",15),("P2",10),("P3",10)):
  got=db.execute("""SELECT sum(introduced_count) FROM arno_v3_run_evidence
  WHERE cohort='OCT2026_P123_NEW_RETROSPECTIVE' AND arm=?""",(arm,)).fetchone()[0]
  require(got,n,"P123 "+arm)
 checked=0
 for run,role,sha,compressed in db.execute("SELECT run_id,role,sha256,zlib_blob FROM arno_v3_asset_bytes"):
  require(digest(zlib.decompress(compressed)),sha,run+" "+role);checked+=1
 require(db.execute("PRAGMA quick_check").fetchone()[0],"ok","SQLite integrity")
 return checked

def main():
 import argparse
 a=argparse.ArgumentParser()
 a.add_argument("--execute",action="store_true")
 opts=a.parse_args()
 items,summary=load_preflight()
 print(json.dumps({"preflight":"PASS","evidence_runs":len(items),
                   "scanner_warning_totals":summary}),flush=True)
 if not opts.execute:return
 if DEST.exists() or PART.exists() or REPORT.exists():
  raise FileExistsError("Sidecar exists; refusing overwrite")
 OUTPUT.mkdir(parents=True,exist_ok=True)
 t=time.monotonic()
 db=sqlite3.connect(str(PART),timeout=15,uri=True)
 try:
  db.execute("ATTACH DATABASE ? AS frozen",("file:"+str(SOURCE_DB)+"?mode=ro",))
  require(db.execute("SELECT count(*) FROM frozen.study_runs").fetchone()[0],68,"original v1 runs")
  sidecar_schema(db)
  change=Counter()
  for item in items:
   old=db.execute("SELECT patch_sha256 FROM frozen.study_runs WHERE run_id=?",
                  (item["run"],)).fetchone()
   if old:require(old[0],item["patch_sha"],"v1 P1 patch "+item["run"])
   change["old" if old else "new"]+=1
   insert_item(db,item,bool(old))
  require(change["old"],7,"preexisting P1")
  require(change["new"],26,"new P2 P3 AC")
  copy_verified_index(db)
  db.execute("INSERT INTO arno_v3_metadata VALUES(?,?)",(
   "relationship_to_v1","Read-only ATTACH: frozen v1 has 68 runs; overlay has 26; 94 combined"))
  db.execute("INSERT INTO arno_v3_metadata VALUES(?,?)",(
   "limitations","Not a standalone replacement for 42GB v1; attach original to query all records"))
  db.commit()
  verified=verify(db)
  db.execute("DETACH DATABASE frozen")
  db.close()
  report={"status":"PASS_WITH_DOCUMENTED_GAPS","preexisting_v1_runs":68,
          "new_normalized_overlay_runs":26,"combined_normalized_runs":94,
          "evidence_runs":33,"embedded_assets_SHA_verified":verified,
          "archive_patch_members_indexed":255,"archive_only_members_unverified":150,
          "final_posthoc_repair_patches_verified":7,
          "unresolved_gaps":16,"P123_and_AC_scanner_totals":summary,
          "original_v1_database":str(SOURCE_DB),"sidecar_database":str(DEST),
          "sidecar_bytes":PART.stat().st_size,
          "duration_seconds":round(time.monotonic()-t,1)}
  tmpreport=OUTPUT/"ARNO_REPLAY_SIDECAR_v3_QA.json.partial"
  tmpreport.write_text(json.dumps(report,indent=2))
  os.replace(PART,DEST)
  os.replace(tmpreport,REPORT)
  print(json.dumps(report,indent=2),flush=True)
 except BaseException:
  try:db.close()
  except Exception:pass
  raise
if __name__=="__main__":main()
