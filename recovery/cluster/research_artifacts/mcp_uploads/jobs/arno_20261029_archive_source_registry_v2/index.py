#!/usr/bin/env python3
"""Index original 2026-10-19 CodeQL export archives with exact on-disk SHA-256.
Read-only by default. --apply adds source-reference metadata, NOT raw archive
bytes, preserving private and potentially sensitive content at its cluster path.
"""
import argparse,concurrent.futures,hashlib,json,sqlite3,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
BASE=R/"ARNO_CODEQL_EXPORT_20261019"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_20261029_archive_source_registry"
MAN=BASE/"EXPORT_SUMMARY.json"
KEY_PREFIX="arno_codeql_oct19_original:"
TABLE="arno_codeql_oct19_original_archive_inventory"
def check(ok,msg):
 if not ok:raise RuntimeError(msg)
def hash_file(item):
 key,name,expected_size,expected_sha,expected_members=item
 p=BASE/name
 check(p.is_file(),"Missing source file "+name)
 check(p.stat().st_size==expected_size,"Original bytes size differs "+name)
 digest=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):digest.update(b)
 actual=digest.hexdigest()
 check(actual==expected_sha,"Original SHA256 differs "+name)
 n=None
 if expected_members is not None:
  with zipfile.ZipFile(p) as z:
   entries=z.infolist()
   n=sum(not x.is_dir() for x in entries)
   check(n==expected_members+1,"Archive physical count not one above frozen manifest count "+name+": "+str(n))
 return {"key":key,"name":name,"relative_path":"ARNO_CODEQL_EXPORT_20261019/"+name,
 "bytes":expected_size,"sha256":actual,"members":expected_members,"physical_members":n,
 "handling":"EXTERNAL_PRIVATE_ORIGINAL_BINARY_NOT_EMBEDDED"}
def load_items():
 d=json.loads(MAN.read_text())
 check(d.get("status")=="COMPLETE","Frozen export manifest incomplete")
 info=[]
 for part in d["part_files"].values():
  info.append((part["file"],part["file"],part["bytes"],part["sha256"],part["member_count"]))
 m=d["master"]
 info.append((m["path"].split("/")[-1],m["path"].split("/")[-1],m["bytes"],m["sha256"],None))
 return d,info
def main():
 pa=argparse.ArgumentParser();pa.add_argument("--apply",action="store_true")
 args=pa.parse_args()
 d,items=load_items()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  result=list(ex.map(hash_file,items))
 check(len(result)==10,"Expected nine parts and one combined handoff")
 source_raw=MAN.read_bytes()
 manifest_sha=hashlib.sha256(source_raw).hexdigest()
 summary={"status":"ORIGINAL_EXPORT_ARCHIVE_CHECKSUMS_VERIFIED","verified_utc":datetime.now(timezone.utc).isoformat(),
 "manifest_sha256":manifest_sha,"raw_files_in_export":d["raw_files"],
 "original_export_exclusions":d["exclusions"],"privacy":"PRIVATE_ARCHIVE_PATHS_ONLY_RAW_ZIP_BYTES_NOT_EMBEDDED",
 "archives":result,"original_source_manifest":"ARNO_CODEQL_EXPORT_20261019/EXPORT_SUMMARY.json"}
 raw=json.dumps(summary,indent=2,sort_keys=True).encode("utf-8")+b"\n"
 conn=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=120)
 try:
  conn.execute("PRAGMA foreign_keys=ON")
  if not args.apply:conn.execute("PRAGMA query_only=ON")
  check(conn.execute("SELECT count(*) FROM arno_d7_final_roots_342").fetchone()[0]==342,"Master D7 regression")
  check(conn.execute("SELECT count(*) FROM arno_experiment_runs").fetchone()[0]==40,"Master experiment regression")
  check(conn.execute("SELECT count(*) FROM sqlite_master WHERE name=? AND type='table'",(TABLE,)).fetchone()[0]==0,"Inventory table already exists")
  check(conn.execute("SELECT count(*) FROM arno_sources WHERE source_key LIKE ?",(KEY_PREFIX+"%",)).fetchone()[0]==0,"Archive sources already present")
  check(conn.execute("SELECT count(*) FROM arno_sources WHERE source_key='arno_codeql_oct19_export_manifest'").fetchone()[0]==0,"Original manifest source already present")
  OUT.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   with (OUT/"PREFLIGHT.json").open("xb") as f:f.write(raw)
   print(json.dumps({"status":"PREFLIGHT_PASS","archived_zip_sources":len(result),
    "total_hashed_bytes":sum(x["bytes"] for x in result),"source_manifest_sha256":manifest_sha},indent=2))
   return
  conn.execute("BEGIN IMMEDIATE")
  conn.execute("""INSERT INTO arno_sources
    (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,
     embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)""",
   ("arno_codeql_oct19_export_manifest","FROZEN_ORIGINAL_EXPORT_MANIFEST",
    "ARNO October 19 frozen CodeQL export manifest",str(MAN),manifest_sha,
    "json/utf-8",source_raw,"EXACT_SHA256_AND_NINE_PARTS_PLUS_MASTER_VERIFIED",
    "Original manifest; 40 export exclusions. Binary archives remain private and unembedded."))
  conn.execute("""CREATE TABLE arno_codeql_oct19_original_archive_inventory (
    source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
    file_name TEXT NOT NULL UNIQUE,relative_path TEXT NOT NULL UNIQUE,
    original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    member_count INTEGER,handling TEXT NOT NULL,
    original_manifest_source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
  )""")
  for a in result:
   source_key=KEY_PREFIX+a["name"]
   conn.execute("""INSERT INTO arno_sources
      (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,
       embedded_bytes,verification,notes)
       VALUES(?,?,?,?,?,?,?,?,?)""",
    (source_key,"ORIGINAL_PRIVATE_BINARY_ARCHIVE",a["name"],str(R/a["relative_path"]),
     a["sha256"],None,None,"EXACT_ON_DISK_SHA256_MATCHES_FROZEN_EXPORT_MANIFEST",
     "Original private binary archive; not embedded to avoid secret propagation. Raw source remains at recorded path."))
   conn.execute("INSERT INTO "+TABLE+" VALUES(?,?,?,?,?,?,?,?)",
    (source_key,a["name"],a["relative_path"],a["bytes"],a["sha256"],a["members"],
     a["handling"],"arno_codeql_oct19_export_manifest"))
  check(conn.execute("SELECT count(*) FROM "+TABLE).fetchone()[0]==10,"Inventory count mismatch")
  check(not conn.execute("PRAGMA foreign_key_check("+TABLE+")").fetchone(),"Inventory FK error")
  conn.commit()
  with (OUT/"LIVE_REPORT.json").open("xb") as f:f.write(raw)
  print(json.dumps({"status":"SOURCE_REFERENCE_IMPORT_COMPLETE","sources_registered":11,
  "binary_archives_referenced":10,"binary_archive_contents_embedded":0,
  "manifest_original_bytes_embedded":len(source_raw),
  "verified_bytes":sum(x["bytes"] for x in result),"report":str(OUT/"LIVE_REPORT.json")},indent=2))
 finally:conn.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("ARCHIVE_SOURCE_REGISTRY_ERROR: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
