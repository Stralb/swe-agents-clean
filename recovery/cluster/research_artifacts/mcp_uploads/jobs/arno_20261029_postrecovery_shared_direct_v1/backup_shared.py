#!/usr/bin/env python3
"""Read-only online SQLite backup to a new shared-storage snapshot.
Never overwrites historical master or any existing destination. No network.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, sqlite3, sys, time

ROOT = Path.home() / "research_artifacts"
SOURCE = ROOT / "ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SNAPSHOT = ROOT / "ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
PART = Path(str(SNAPSHOT) + ".shared_direct_v1.partial")
CERT = Path(str(SNAPSHOT) + ".json")
PARTCERT = Path(str(CERT) + ".shared_direct_v1.partial")
NEEDED = {
    "arno_d7_final_roots_342":342,
    "arno_experiment_runs":40,
    "arno_generated_patches":40,
    "arno_experiment_scans":40,
    "arno_new70_final_findings":237,
    "arno_new70_final_producing_changes":133,
    "arno_new70_final_unresolved":61,
    "arno_claim_status_supersession_20261029":10,
    "arno_codeql_oct19_original_archive_inventory":10,
    "arno_screen65_before_sarif_candidates_20261029":28
}

def log(**fields):
    print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), **fields}), flush=True)

def check(cond, message):
    if not cond:
        raise RuntimeError(message)

def readonly(path):
    con = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=120)
    con.execute("PRAGMA query_only=ON")
    return con

def census(con):
    return {table: con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in NEEDED}

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8*1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def main():
    check(SOURCE.is_file(), "Original master missing")
    check(not SNAPSHOT.exists() and not CERT.exists(), "A final backup/certificate already exists")
    check(not PART.exists() and not PARTCERT.exists(), "Temporary backup path already exists")
    size = SOURCE.stat().st_size
    sv = os.statvfs(SNAPSHOT.parent)
    shared_free = sv.f_bavail*sv.f_frsize
    check(shared_free > size + 6*1024**3, "Insufficient shared storage")
    os.umask(0o077)
    src = readonly(SOURCE)
    try:
        beginning=census(src)
        check(beginning==NEEDED, "Frozen source census mismatch: " + repr(beginning))
        source_pages = src.execute("PRAGMA page_count").fetchone()[0]
        source_page_size = src.execute("PRAGMA page_size").fetchone()[0]
        PART.open("xb").close()
        dst=sqlite3.connect(str(PART),timeout=120)
        last=[-1]
        def progress(status, remaining, total):
            done=total-remaining
            bucket=done//1000000
            if bucket>last[0]:
                last[0]=bucket
                log(phase="backup_progress",completed_pages=done,total_pages=total)
        try:
            src.backup(dst,pages=16384,progress=progress,sleep=0.1)
        finally:
            dst.close()
        log(phase="online_sqlite_backup_complete",source_pages=source_pages,page_size=source_page_size)
    finally:
        src.close()

    replica=readonly(PART)
    try:
        qc=replica.execute("PRAGMA quick_check").fetchone()[0]
        check(qc=="ok", "SQLite quick_check failed: " + repr(qc))
        actual=census(replica)
        check(actual==beginning, "Backup table census mismatch")
        end_pages=replica.execute("PRAGMA page_count").fetchone()[0]
        check(end_pages>0, "Backup has zero pages")
    finally:
        replica.close()
    check(PART.stat().st_size>=size//2, "Snapshot unexpectedly small")
    first=sha256(PART)
    second=sha256(PART)
    check(first==second, "Repeated SHA-256 mismatch")
    report={
        "status":"VERIFIED_POST_RECOVERY_BACKUP",
        "method":"SQLITE_ONLINE_BACKUP_DIRECT_SHARED_STORAGE",
        "verified_at_utc":datetime.now(timezone.utc).isoformat(),
        "snapshot":str(SNAPSHOT),
        "snapshot_size":PART.stat().st_size,
        "snapshot_sha256":first,
        "quick_check":"ok",
        "counts":actual,
        "source_opened_read_only":True,
        "original_master_unmodified":True,
        "huggingface_touched":False,
        "note":"SQLite point-in-time online snapshot to new shared-storage file; quick_check, exact critical census and repeated SHA-256 verified. No local scratch copy."
    }
    with PARTCERT.open("x",encoding="utf8") as f:
        json.dump(report,f,indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(PART,0o440)
    check(not SNAPSHOT.exists() and not CERT.exists(), "Final destination appeared during verification")
    os.link(PART,SNAPSHOT)
    os.unlink(PART)
    os.link(PARTCERT,CERT)
    os.unlink(PARTCERT)
    log(**report)

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        print("SHARED_DIRECT_BACKUP_FAILED " + repr(e),file=sys.stderr,flush=True)
        # Only discard unique, incomplete temporary files. Never delete final snapshot or source.
        if not SNAPSHOT.exists():
            for path in (PART,PARTCERT):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
        sys.exit(1)
