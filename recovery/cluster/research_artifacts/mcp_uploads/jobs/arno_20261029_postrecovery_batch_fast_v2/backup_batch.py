#!/usr/bin/env python3
"""Verified post-recovery SQLite online backup to local scratch, then shared snapshot.
Reads original master in read-only mode; no Hugging Face access. Fails closed.
"""
import hashlib,json,os,sqlite3,sys,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
SRC=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SNAP=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
PART=Path(str(SNAP)+".partial")
CERT=Path(str(SNAP)+".json")
NEEDED={"arno_d7_final_roots_342":342,"arno_experiment_runs":40,
"arno_generated_patches":40,"arno_experiment_scans":40,
"arno_new70_final_findings":237,"arno_new70_final_producing_changes":133,
"arno_new70_final_unresolved":61,"arno_claim_status_supersession_20261029":10,
"arno_codeql_oct19_original_archive_inventory":10,
"arno_screen65_before_sarif_candidates_20261029":28}
def ck(ok,msg):
 if not ok:raise RuntimeError(msg)
def out(x):print(json.dumps({"utc":datetime.now(timezone.utc).isoformat(),**x}),flush=True)
def counts(conn):
 return {t:conn.execute("SELECT count(*) FROM "+t).fetchone()[0] for t in NEEDED}
def read():
 c=sqlite3.connect("file:"+str(SRC)+"?mode=ro",uri=True,timeout=120)
 c.execute("PRAGMA query_only=ON")
 return c
def write_backup(local):
 src=read()
 try:
  initial=counts(src)
  ck(initial==NEEDED,"Master research census changed, refusing backup")
  pages=src.execute("PRAGMA page_count").fetchone()[0]
  page_size=src.execute("PRAGMA page_size").fetchone()[0]
  last=[-1]
  dst=sqlite3.connect(str(local),timeout=120)
  def status(state,remaining,total):
   completed=total-remaining
   bucket=completed//1000000
   if bucket>last[0]:
    last[0]=bucket
    out({"phase":"online_snapshot_backup","completed_pages":completed,"total_pages":total})
  try:
   src.backup(dst,pages=4096,progress=status,sleep=0.1)
  finally:dst.close()
  out({"phase":"sqlite_online_backup_complete","pages":pages,"page_size":page_size})
 finally:src.close()
 return initial
def main():
 ck(SRC.is_file() and not SNAP.exists() and not PART.exists() and not CERT.exists(),"Source missing or snapshot destination already exists")
 free=os.statvfs("/tmp")
 free_bytes=free.f_bavail*free.f_frsize
 size=SRC.stat().st_size
 ck(free_bytes>size+6*1024**3,"Insufficient local scratch")
 ck(os.statvfs(SNAP.parent).f_bavail*os.statvfs(SNAP.parent).f_frsize>size+6*1024**3,"Shared storage too full")
 os.umask(0o077)
 with tempfile.TemporaryDirectory(prefix="arno_post_recovery_",dir="/tmp") as temp:
  local=Path(temp)/"sqlite_snapshot.sqlite"
  initial=write_backup(local)
  lc=sqlite3.connect("file:"+str(local)+"?mode=ro",uri=True,timeout=120)
  lc.execute("PRAGMA query_only=ON")
  try:
   qc=lc.execute("PRAGMA quick_check").fetchone()[0]
   ck(qc=="ok","Local backup SQLite integrity failed: "+str(qc))
   ck(counts(lc)==initial,"Local backup row counts differ")
  finally:lc.close()
  out({"phase":"local_sqlite_quick_check_pass","result":qc})
  digest=hashlib.sha256()
  with local.open("rb") as read_file,PART.open("xb") as shared_file:
   copied=0
   while True:
    chunk=read_file.read(8*1024*1024)
    if not chunk:break
    digest.update(chunk);shared_file.write(chunk);copied+=len(chunk)
    if copied%(4*1024**3)<8*1024*1024:out({"phase":"snapshot_to_shared","gib":round(copied/2**30,2)})
   shared_file.flush();os.fsync(shared_file.fileno())
  ck(copied==local.stat().st_size,"Shared snapshot incomplete")
  localsha=digest.hexdigest()
  h=hashlib.sha256()
  with PART.open("rb") as f:
   for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
  ck(h.hexdigest()==localsha,"Shared snapshot digest mismatch")
  ck(not SNAP.exists() and not CERT.exists(),"Post-recovery snapshot collision")
  PART.rename(SNAP);os.chmod(SNAP,0o440)
  report={"status":"VERIFIED_POST_RECOVERY_BACKUP",
   "verified_at_utc":datetime.now(timezone.utc).isoformat(),
   "snapshot":str(SNAP),"snapshot_size":SNAP.stat().st_size,
   "snapshot_sha256":localsha,"quick_check":"ok",
   "counts":initial,"original_master_unmodified":True,"huggingface_touched":False,
   "note":"SQLite consistent online snapshot of the 2026-10-29 post-recovery master, checked on local compute-node scratch and compared byte-for-byte against shared copy."}
  with CERT.open("x") as f:json.dump(report,f,indent=2)
  out(report)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("POST_RECOVERY_BACKUP_FAILED "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
