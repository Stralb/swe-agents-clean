#!/usr/bin/env python3
"""Independent local-scratch SQLite backup verification on bigbatch.
Source master and shared partial are opened read-only. No renames or master writes.
Local copy is deleted on exit, including failures. Prints checkpoints as it progresses.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,sqlite3,sys,tempfile,time
R=Path.home()/"research_artifacts"
SRC=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
PART=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_PRE_OCT28_RQ3_NORMALIZATION.sqlite.partial"
DEST=R/"mcp_uploads/jobs/arno_20261029_bigbatch_local_verify/REPORT.json"
EXPECTED_BYTES=37462716416
TABLES=["arno_root_decisions","arno_pc_root_lineage","arno_d7_final_M_roots_233",
        "arno_rq3_owp14_run_scans","arno_rq3_owp14_verified_patch_bytes",
        "arno_experiment_runs","arno_experiment_scans","arno_generated_patches"]
def check(ok,why):
 if not ok:raise RuntimeError(why)
def conn(path):
 c=sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True,timeout=90)
 c.execute("PRAGMA query_only=ON")
 return c
def summary(c):
 return {"table_counts":{t:c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in TABLES},
         "page_count":c.execute("PRAGMA page_count").fetchone()[0],
         "page_size":c.execute("PRAGMA page_size").fetchone()[0]}
def progress(name,extra=None):
 print(json.dumps({"phase":name,"utc":datetime.now(timezone.utc).isoformat(),**(extra or {})}),flush=True)
def main():
 check(SRC.exists() and PART.exists(),"Master or partial snapshot absent")
 check(SRC.stat().st_size==PART.stat().st_size==EXPECTED_BYTES,"Unexpected source/partial size")
 check(not Path(str(PART)+"-journal").exists(),"Partial copy still in SQLite transaction")
 baseline=conn(SRC)
 try:src_qc=summary(baseline)
 finally:baseline.close()
 p=conn(PART)
 try:partial_qc=summary(p)
 finally:p.close()
 check(src_qc==partial_qc,"Source/partial table counts or pages differ")
 check(src_qc["table_counts"]["arno_experiment_runs"]==0,"Master already advanced; abort")
 st0=PART.stat()
 progress("shared_source_metadata_pass",src_qc)
 disk=os.statvfs("/tmp")
 free=disk.f_bavail*disk.f_frsize
 check(free>EXPECTED_BYTES+5*(1024**3),"Not enough local /tmp scratch for safe copy")
 os.umask(0o077)
 t=time.monotonic()
 with tempfile.TemporaryDirectory(prefix="arno_verified_backup_",dir="/tmp") as d:
  local=Path(d)/"master_backup_copy.sqlite"
  h=hashlib.sha256()
  with PART.open("rb") as s,local.open("xb") as o:
   i=0
   while True:
    b=s.read(16*1024*1024)
    if not b:break
    h.update(b);o.write(b);i+=len(b)
    if i%(4*1024**3)<16*1024*1024:
     progress("copying_snapshot",{"copied_gib":round(i/2**30,2)})
   o.flush()
  check(i==EXPECTED_BYTES,"Incomplete copied backup")
  st1=PART.stat()
  check(st1.st_size==st0.st_size and st1.st_mtime_ns==st0.st_mtime_ns,"Backup changed while copying")
  digest=h.hexdigest()
  progress("local_copy_sha256",{"sha256":digest,"copy_seconds":round(time.monotonic()-t,1)})
  t2=time.monotonic()
  c=conn(local)
  try:
   qc=c.execute("PRAGMA quick_check").fetchone()[0]
   check(qc=="ok","SQLite local quick_check: "+str(qc))
   check(summary(c)==src_qc,"SQLite local summary mismatch")
  finally:c.close()
  progress("local_quick_check_pass",{"quick_check_seconds":round(time.monotonic()-t2,1)})
  result={"status":"BIGBATCH_LOCAL_SCRATCH_VERIFIED","utc":datetime.now(timezone.utc).isoformat(),
   "source_snapshot_path":str(PART),"source_master_path":str(SRC),
   "source_and_snapshot_counts_match":True,"snapshot_bytes":EXPECTED_BYTES,
   "snapshot_sha256":digest,"sqlite_quick_check":"ok","page_count":src_qc["page_count"],
   "page_size":src_qc["page_size"],"counts":src_qc["table_counts"],
   "local_copy_removed_after_check":True,"original_snapshot_untouched":True,
   "master_untouched":True,"storage":"bigbatch node local /tmp","node":os.uname().nodename}
  check(not DEST.exists(),"Report target already exists")
  DEST.write_text(json.dumps(result,indent=2),encoding="utf-8")
  print(json.dumps(result,indent=2),flush=True)
if __name__=="__main__":
 try:main()
 except BaseException as e:
  print("LOCAL_BACKUP_VERIFY_FAILED: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
