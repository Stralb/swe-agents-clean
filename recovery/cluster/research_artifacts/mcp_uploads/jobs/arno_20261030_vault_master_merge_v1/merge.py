#!/usr/bin/env python3
"""Append lossless archive vault into live master ONLY after verified backups and baseline registry.
Never updates existing rows or historical tables. Maintains all source archive bytes.
"""
from pathlib import Path
import hashlib,json,os,sqlite3,sys
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
V=R/"ARNO_MASTER_DB/ARNO_EVIDENCE_VAULT_20261030.sqlite"
VC=Path(str(V)+".json")
SNAP=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
SC=Path(str(SNAP)+".json")
OUT=R/"mcp_uploads/jobs/arno_20261030_vault_master_merge_v1/REPORT.json"
PREFIX="arno_archive_vault_"
TABLES=[PREFIX+x for x in ("objects","chunks","members","sources","metadata")]
def check(ok,message):
 if not ok:raise RuntimeError(message)
def hashfile(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main():
 check(DB.is_file() and V.is_file() and SNAP.is_file() and VC.is_file() and SC.is_file(),"Master, vault, or verified backup missing")
 check(not OUT.exists(),"Merge report already exists")
 vc=json.loads(VC.read_text());sc=json.loads(SC.read_text())
 check(vc.get("status")=="VERIFIED_LOSSLESS_EVIDENCE_VAULT" and vc.get("sqlite_quick_check")=="ok" and vc.get("all_objects_reconstructed_and_sha256_verified") is True,"Vault certificate not valid")
 check(vc.get("vault_path")==str(V) and vc.get("vault_bytes")==V.stat().st_size and vc.get("vault_sha256")==hashfile(V),"Vault raw digest mismatch")
 check(sc.get("status")=="VERIFIED_POST_RECOVERY_BACKUP" and sc.get("quick_check")=="ok" and sc.get("snapshot")==str(SNAP) and sc.get("snapshot_size")==SNAP.stat().st_size,"Post-recovery backup certificate not valid")
 check(sc.get("source_opened_read_only") is True or sc.get("original_master_unmodified") is True,"Backup certificate inconsistent")
 con=sqlite3.connect(str(DB),timeout=180)
 con.execute("PRAGMA foreign_keys=ON")
 con.execute("PRAGMA busy_timeout=180000")
 try:
  con.execute("ATTACH DATABASE ? AS vault",("file:"+str(V)+"?mode=ro",))
  old=con.execute("SELECT COUNT(*) FROM arno_owp14_exact_scan_baseline_links_20261029").fetchone()[0]
  check(old==40,"Preceding baseline-source import not verified")
  check(con.execute("SELECT COUNT(*) FROM arno_sources").fetchone()[0]>=118,"Unexpected master source registry")
  for table in TABLES:
   check(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]==0,"Archive vault tables already exist: "+table)
  total=con.execute("SELECT COUNT(*) FROM vault.vault_objects").fetchone()[0]
  members=con.execute("SELECT COUNT(*) FROM vault.vault_members").fetchone()[0]
  sources=con.execute("SELECT COUNT(*) FROM vault.source_coverage").fetchone()[0]
  segments=con.execute("SELECT COUNT(*) FROM vault.vault_chunks").fetchone()[0]
  check(total>=52 and members==4610 and sources>=54 and segments>800,"Vault evidence census invalid")
  con.execute("BEGIN IMMEDIATE")
  con.executescript("""
   CREATE TABLE arno_archive_vault_objects(
    object_key TEXT PRIMARY KEY,source_kind TEXT NOT NULL,source_locator TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    segment_count INTEGER NOT NULL,case_id INTEGER,source_key TEXT
   );
   CREATE TABLE arno_archive_vault_chunks(
    object_key TEXT NOT NULL REFERENCES arno_archive_vault_objects(object_key),
    sequence INTEGER NOT NULL,bytes BLOB NOT NULL,content_sha256 TEXT NOT NULL,
    PRIMARY KEY(object_key,sequence)
   );
   CREATE TABLE arno_archive_vault_members(
    archive_name TEXT NOT NULL,member_path TEXT NOT NULL,case_id TEXT,
    role TEXT NOT NULL,sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    indexed_in_master INTEGER NOT NULL,matched_master_tables TEXT,
    PRIMARY KEY(archive_name,member_path)
   );
   CREATE TABLE arno_archive_vault_sources(
    source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
    kind TEXT NOT NULL,original_locator TEXT NOT NULL,expected_sha256 TEXT,
    vault_object_key TEXT,coverage_status TEXT NOT NULL
   );
   CREATE TABLE arno_archive_vault_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  """)
  con.execute("INSERT INTO arno_archive_vault_objects SELECT * FROM vault.vault_objects")
  con.execute("INSERT INTO arno_archive_vault_chunks SELECT * FROM vault.vault_chunks")
  con.execute("INSERT INTO arno_archive_vault_members SELECT * FROM vault.vault_members")
  con.execute("INSERT INTO arno_archive_vault_sources SELECT * FROM vault.source_coverage")
  con.execute("INSERT INTO arno_archive_vault_metadata VALUES (?,?)",("source_vault_sha256",vc["vault_sha256"]))
  con.execute("INSERT INTO arno_archive_vault_metadata VALUES (?,?)",("merge_utc",datetime.now(timezone.utc).isoformat()))
  con.execute("INSERT INTO arno_archive_vault_metadata VALUES (?,?)",("content_validation","original bytes checked in vault; append-only copy"))
  for table,count in ((PREFIX+"objects",total),(PREFIX+"chunks",segments),(PREFIX+"members",members),(PREFIX+"sources",sources)):
   check(con.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]==count,"Postimport count mismatch "+table)
   check(not con.execute("PRAGMA foreign_key_check("+table+")").fetchone(),"Foreign key violations "+table)
  con.commit()
  report={"status":"ARCHIVED_EVIDENCE_LOSSLESSLY_INTEGRATED_IN_MASTER",
   "merged_utc":datetime.now(timezone.utc).isoformat(),
   "master_path":str(DB),"master_bytes_after":DB.stat().st_size,
   "vault_sha256":vc["vault_sha256"],
   "archive_objects":total,"archive_chunks":segments,"indexed_archive_members":members,"source_coverage_records":sources,
   "original_archive_bytes_reconstructible":True,
   "historic_source_rows_overwritten":False,
   "huggingface_updated":False,
   "scientific_limits":"Historical agent traces not archived cannot be reconstructed. This vault records archive membership and case IDs but does not certify all human decisions or security exploitability."}
  OUT.parent.mkdir(parents=True,exist_ok=True)
  with OUT.open("x") as f:json.dump(report,f,indent=2)
  print(json.dumps(report,sort_keys=True),flush=True)
 finally:con.close()
if __name__=="__main__":
 try:main()
 except Exception as e:print("MASTER_VAULT_MERGE_FAILED "+repr(e),file=sys.stderr,flush=True);sys.exit(1)
