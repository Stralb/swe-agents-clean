#!/usr/bin/env python3
"""Create a verified compact SQLite recovery delta after the 40 baseline links commit.
Read-only access to original master; new sidecar contains ONLY new OWP provenance
tables + their arno_sources records. No raw input ZIPs, no secrets, no HF.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sqlite3,os,sys
R=Path.home()/"research_artifacts"
MASTER=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
DEST=R/"ARNO_MASTER_DB/snapshots/ARNO_OWP14_POSTBACKUP_PROVENANCE_DELTA_20261029.sqlite"
CERT=Path(str(DEST)+".json")
TEMP=Path(str(DEST)+".partial")
TABLES={
"arno_owp14_original_input_packet_inventory_20261029":42,
"arno_owp14_input_repo_equivalence_20261029":14,
"arno_owp14_exact_scan_baseline_links_20261029":40
}
SOURCE_KEYS=[
"owp14_original_42_packet_index_20261029",
"owp14_42_input_repo_tree_equivalence_20261029",
"owp14_exact_baseline_sha_crosswalk_20261029"]
PREFIX="owp14_original_packet_20261029:"
def need(x,msg):
 if not x:raise RuntimeError(msg)
def qident(x):return '"'+x.replace('"','""')+'"'
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for buf in iter(lambda:f.read(1024*1024),b""):h.update(buf)
 return h.hexdigest()
def main():
 need(MASTER.exists(),"Original master missing")
 need(not DEST.exists() and not CERT.exists() and not TEMP.exists(),"Delta already exists; abort rather than overwrite")
 os.umask(0o077)
 source=sqlite3.connect("file:"+str(MASTER)+"?mode=ro",uri=True,timeout=120)
 source.execute("PRAGMA query_only=ON")
 try:
  counts={k:source.execute("SELECT COUNT(*) FROM "+qident(k)).fetchone()[0] for k in TABLES}
  need(counts==TABLES,"Original source table row counts invalid: "+str(counts))
  for key in SOURCE_KEYS:
   need(source.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key=?",(key,)).fetchone()[0]==1,"Missing source reference: "+key)
  need(source.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key LIKE ?",(PREFIX+"%",)).fetchone()[0]==42,"Missing packet archive source refs")
  need(source.execute("SELECT COUNT(*) FROM arno_experiment_scans").fetchone()[0]==40,"Underlying scan census regressed")
  cases=source.execute("SELECT COUNT(DISTINCT case_id),COUNT(*) FROM arno_owp14_exact_scan_baseline_links_20261029").fetchone()
  need(cases==(14,40),"Case/scan linkage mismatch")
  linked=source.execute("SELECT COUNT(*) FROM arno_owp14_exact_scan_baseline_links_20261029 WHERE exact_match_status='BYTE_IDENTICAL_FIRST_WAVE_SARIF_AND_PACKET_SHA' AND historical_pr_revision_equivalence='NOT_VERIFIED'").fetchone()[0]
  need(linked==40,"Linked hashes unverified or overstated")
  # Create a portable sidecar: preserve original CREATE SQL and raw typed rows,
  # with FOREIGN KEY enforcement off because this is a subset, not a second master.
  dst=sqlite3.connect(str(TEMP))
  try:
   dst.execute("PRAGMA journal_mode=DELETE")
   dst.execute("PRAGMA foreign_keys=OFF")
   dst.execute("BEGIN")
   dst.execute("CREATE TABLE _delta_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
   src_schema=source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='arno_sources'").fetchone()[0]
   need(src_schema and "CREATE TABLE" in src_schema,"Original sources schema absent")
   dst.execute(src_schema)
   s_cols=[r[1] for r in source.execute("PRAGMA table_info(arno_sources)")]
   cols=",".join(qident(c) for c in s_cols)
   sql="SELECT "+cols+" FROM arno_sources WHERE source_key IN (?,?,?) OR source_key LIKE ? ORDER BY source_key"
   refs=source.execute(sql,(*SOURCE_KEYS,PREFIX+"%")).fetchall()
   need(len(refs)==45,"Expected 45 exact packet+audit source rows; found "+str(len(refs)))
   dst.executemany("INSERT INTO arno_sources ("+cols+") VALUES("+",".join("?" for _ in s_cols)+")",refs)
   for table,expected in TABLES.items():
    create=source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]
    need(create,"Missing original CREATE DDL "+table)
    dst.execute(create)
    headers=[r[1] for r in source.execute("PRAGMA table_info("+qident(table)+")")]
    cols=",".join(qident(c) for c in headers)
    rows=source.execute("SELECT "+cols+" FROM "+qident(table)).fetchall()
    need(len(rows)==expected,"Source row count changed "+table)
    dst.executemany("INSERT INTO "+qident(table)+" ("+cols+") VALUES ("+",".join("?" for _ in headers)+")",rows)
   meta={
    "scope":"OWP14 new metadata added after 2026-10-29 backup started",
    "source_db":str(MASTER),
    "table_counts":TABLES,
    "source_records":45,
    "created_utc":datetime.now(timezone.utc).isoformat(),
    "policy":"Private original ZIP contents not embedded; scanner and historic facts are referenced."
   }
   dst.executemany("INSERT INTO _delta_meta VALUES(?,?)",[(k,json.dumps(v,sort_keys=True)) for k,v in meta.items()])
   dst.commit()
   ok=dst.execute("PRAGMA quick_check").fetchone()[0]
   need(ok=="ok","Delta SQLite quick_check failed: "+str(ok))
   for table,expected in TABLES.items():
    need(dst.execute("SELECT COUNT(*) FROM "+qident(table)).fetchone()[0]==expected,"Delta counts mismatch")
  finally:dst.close()
 finally:source.close()
 digest=sha(TEMP)
 need(TEMP.stat().st_size<20_000_000,"Unusually large sidecar: privacy concern")
 os.chmod(TEMP,0o440)
 TEMP.rename(DEST)
 cert={"status":"VERIFIED_OWP14_PROVENANCE_DELTA","date_utc":datetime.now(timezone.utc).isoformat(),
 "source_master":str(MASTER),"sidecar_path":str(DEST),"sidecar_bytes":DEST.stat().st_size,
 "sidecar_sha256":digest,"sqlite_quick_check":"ok","table_counts":TABLES,
 "source_records":45,"archive_zip_bytes_embedded":False,"huggingface_updated":False,
 "note":"Compact portable subset; dependent original case/scan tables remain in main master/verified base backup. Avoid treating this delta alone as restorable full database."}
 with CERT.open("x") as f:json.dump(cert,f,indent=2)
 print(json.dumps(cert,indent=2),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("PROVENANCE_DELTA_FAILED "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
