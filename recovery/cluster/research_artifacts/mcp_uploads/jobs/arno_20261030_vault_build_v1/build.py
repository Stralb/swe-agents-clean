#!/usr/bin/env python3
"""Lossless immutable SQLite archive vault; no writes to the research master.
Stores complete original ZIP bytes in small ordered BLOB chunks, plus source/member links.
"""
import os,csv,sqlite3,hashlib,json,sys,time
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
MASTER=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ROOT=R/"ARNO_CODEQL_EXPORT_20261019"
AUDIT=R/"mcp_uploads/jobs/arno_20261030_archive_audit_v1/ALL_MEMBERS.csv"
OUT=R/"ARNO_MASTER_DB/ARNO_EVIDENCE_VAULT_20261030.sqlite"
TMP=Path(str(OUT)+".partial")
CERT=Path(str(OUT)+".json")
REPORT=R/"mcp_uploads/jobs/arno_20261030_vault_build_v1/REPORT.json"
CHUNK=4*1024*1024
def req(ok,why):
 if not ok:raise RuntimeError(why)
def sha_bytes(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(CHUNK),b""):h.update(b)
 return h.hexdigest()
def role(member):
 name=Path(member).name.lower()
 if name.endswith(".sarif"):return "SARIF"
 if name.endswith((".patch",".diff")):return "PATCH"
 if name.endswith((".zip",".gz",".tar")):return "ARCHIVE"
 if name.endswith(".log"):return "LOG"
 if name.endswith((".json",".jsonl")):return "JSON"
 if name.endswith((".csv",".tsv")):return "TABULAR"
 if name.endswith((".py",".sh",".sbatch",".js",".ts",".yml",".yaml")):return "SCRIPT_OR_CONFIG"
 if "prompt" in name or "trace" in name or "trajectory" in name:return "PROMPT_TRACE_CANDIDATE"
 if name.endswith((".md",".txt")):return "TEXT"
 return "OTHER"
def create_schema(c):
 c.executescript("""
 PRAGMA foreign_keys=ON;
 CREATE TABLE vault_objects(
  object_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_locator TEXT NOT NULL,
  expected_sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL, segment_count INTEGER NOT NULL,
  case_id INTEGER, source_key TEXT
 );
 CREATE TABLE vault_chunks(
  object_key TEXT NOT NULL REFERENCES vault_objects(object_key),
  sequence INTEGER NOT NULL, bytes BLOB NOT NULL, content_sha256 TEXT NOT NULL,
  PRIMARY KEY(object_key,sequence)
 );
 CREATE TABLE vault_members(
  archive_name TEXT NOT NULL, member_path TEXT NOT NULL, case_id TEXT,
  role TEXT NOT NULL, sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL,
  indexed_in_master INTEGER NOT NULL, matched_master_tables TEXT,
  PRIMARY KEY(archive_name,member_path)
 );
 CREATE TABLE source_coverage(
  source_key TEXT PRIMARY KEY,kind TEXT NOT NULL,original_locator TEXT NOT NULL,
  expected_sha256 TEXT,vault_object_key TEXT,coverage_status TEXT NOT NULL
 );
 CREATE TABLE vault_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 """)
def put(c,key,kind,locator,expected_sha,expected_size,case_id=None,source_key=None):
 p=Path(locator)
 req(p.is_file(),"Missing original source: "+str(p))
 req(p.stat().st_size==expected_size,"Original size mismatch: "+str(p))
 num=(expected_size+CHUNK-1)//CHUNK
 c.execute("INSERT INTO vault_objects VALUES(?,?,?,?,?,?,?,?)",
  (key,kind,str(p),expected_sha,expected_size,num,case_id,source_key))
 h=hashlib.sha256();counter=0
 with p.open("rb") as f:
  while True:
   b=f.read(CHUNK)
   if not b:break
   h.update(b)
   c.execute("INSERT INTO vault_chunks VALUES(?,?,?,?)",
    (key,counter,sqlite3.Binary(b),hashlib.sha256(b).hexdigest()))
   counter+=1
 req(counter==num and h.hexdigest()==expected_sha,"Source digest mismatch for "+key)
 c.commit()
 print("VAULT_OBJECT",key,expected_size,"segments",counter,flush=True)
def main():
 req(MASTER.is_file() and AUDIT.is_file(),"Required frozen inputs absent")
 req(not OUT.exists() and not TMP.exists() and not CERT.exists() and not REPORT.exists(),"Vault output collision")
 src=sqlite3.connect("file:"+str(MASTER)+"?mode=ro",uri=True,timeout=120)
 src.execute("PRAGMA query_only=ON")
 archive_records=src.execute("SELECT file_name,original_bytes,sha256 FROM arno_codeql_oct19_original_archive_inventory ORDER BY file_name").fetchall()
 refs=src.execute("""SELECT source_key,source_kind,source_locator,source_sha256 FROM arno_sources
  WHERE embedded_bytes IS NULL ORDER BY source_key""").fetchall()
 req(len(archive_records)==10 and len(refs)>=54,"Frozen reference census disagrees")
 expected_members=0
 with AUDIT.open(newline="",encoding="utf8") as f:
  rows=list(csv.DictReader(f))
 req(len(rows)==4610,"Frozen direct-archive member census changed")
 os.umask(0o077)
 c=sqlite3.connect(str(TMP),timeout=120)
 try:
  c.execute("PRAGMA journal_mode=OFF")
  c.execute("PRAGMA synchronous=OFF")
  create_schema(c);c.commit()
  for filename,size,digest in archive_records:
   put(c,"archive:"+filename,"ORIGINAL_ARCHIVE",ROOT/filename,digest,size)
  copied=0;skipped=0
  for sk,kind,locator,digest in refs:
   obj=None;status="EXTERNAL_NOT_COPIED"
   if sk.startswith("arno_codeql_oct19_original:"):
    obj="archive:"+sk.split(":",1)[1];status="SOURCE_STORED_IN_VAULT"
   elif sk.startswith("owp14_original_packet_20261029:"):
    p=Path(locator)
    req(p.is_file(),"Missing original packet "+sk)
    obj="packet:"+sk
    put(c,obj,"ORIGINAL_OWP14_INPUT_PACKET",locator,digest,p.stat().st_size,
        int(sk.split(":",1)[1].split("_",1)[0]),sk)
    status="SOURCE_STORED_IN_VAULT";copied+=1
   elif kind=="original_workbook":
    p=Path(locator)
    if p.is_file() and digest:
     obj="workbook:"+sk;put(c,obj,"ORIGINAL_WORKBOOK",locator,digest,p.stat().st_size,source_key=sk)
     status="SOURCE_STORED_IN_VAULT";copied+=1
    else:skipped+=1
   else:skipped+=1
   c.execute("INSERT INTO source_coverage VALUES(?,?,?,?,?,?)",(sk,kind,locator,digest,obj,status))
  for r in rows:
   c.execute("INSERT INTO vault_members VALUES(?,?,?,?,?,?,?,?)",(
    r["archive"],r["member"],r["case_id"] or None,role(r["member"]),
    r["sha256"],int(r["size"]),int(r["digest_registered"]),r["matched_tables"]))
   expected_members+=1
  c.executemany("INSERT INTO vault_meta VALUES(?,?)",[
   ("created_utc",datetime.now(timezone.utc).isoformat()),
   ("purpose","LOSSLESS_PRIVATE_EVIDENCE_ARCHIVE_VAULT"),
   ("master_modified","false"),
   ("hf_modified","false"),
   ("chunk_size",str(CHUNK)),
   ("original_index_report",str(AUDIT))
  ])
  c.commit()
  req(c.execute("SELECT COUNT(*) FROM vault_members").fetchone()[0]==4610,"Member count mismatch")
  req(c.execute("PRAGMA quick_check").fetchone()[0]=="ok","SQLite quick_check failed")
  records=c.execute("SELECT object_key,original_bytes,expected_sha256,segment_count FROM vault_objects ORDER BY object_key").fetchall()
  for key,size,digest,count in records:
   h=hashlib.sha256();total=0;n=0
   for (part,part_sha) in c.execute("SELECT bytes,content_sha256 FROM vault_chunks WHERE object_key=? ORDER BY sequence",(key,)):
    req(hashlib.sha256(part).hexdigest()==part_sha,"Chunk corruption "+key)
    h.update(part);total+=len(part);n+=1
   req(total==size and n==count and h.hexdigest()==digest,"Vault object reconstruction digest failure "+key)
  summary={
   "status":"VERIFIED_LOSSLESS_EVIDENCE_VAULT",
   "created_utc":datetime.now(timezone.utc).isoformat(),
   "vault_path":str(OUT),"vault_bytes":TMP.stat().st_size,
   "archived_outer_zips":len(archive_records),"original_case_packets":42,
   "objects":len(records),"member_index":expected_members,
   "external_refs":len(refs),
   "stored_external_refs":c.execute("SELECT COUNT(*) FROM source_coverage WHERE coverage_status='SOURCE_STORED_IN_VAULT'").fetchone()[0],
   "external_refs_not_embedded":c.execute("SELECT COUNT(*) FROM source_coverage WHERE coverage_status='EXTERNAL_NOT_COPIED'").fetchone()[0],
   "sqlite_quick_check":"ok",
   "all_objects_reconstructed_and_sha256_verified":True,
   "original_master_unmodified":True,"huggingface_updated":False,
   "limits":"A lossless private vault of available archives and OWP14 packets, not proof that every historical agent trace was archived. The 37GB baseline SQLite is not duplicated inside vault."
  }
 finally:c.close();src.close()
 summary["vault_sha256"]=sha_bytes(TMP)
 os.chmod(TMP,0o440)
 with CERT.open("x",encoding="utf8") as f:json.dump(summary,f,indent=2)
 os.link(TMP,OUT);os.unlink(TMP)
 REPORT.parent.mkdir(parents=True,exist_ok=True)
 with REPORT.open("x",encoding="utf8") as f:json.dump(summary,f,indent=2)
 print(json.dumps(summary,sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:print("EVIDENCE_VAULT_FAILED "+repr(e),file=sys.stderr,flush=True);sys.exit(1)
