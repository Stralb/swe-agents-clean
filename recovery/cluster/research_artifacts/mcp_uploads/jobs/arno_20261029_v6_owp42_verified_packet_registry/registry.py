#!/usr/bin/env python3
"""Verifies original 42 OWP input ZIP bytes against frozen packet index.
--apply appends path-only, SHA256-verified inventory to ARNO master.
Never extracts or embeds ZIPs, source code, secrets, or agent-generated patches.
"""
import argparse,csv,hashlib,json,sqlite3,zlib,sys
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
D=R/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_20261029_v6_owp42_verified_packet_registry"
T="arno_owp14_original_input_packet_inventory_20261029"
INDEX_KEY="owp14_original_42_packet_index_20261029"
KEY_PREFIX="owp14_original_packet_20261029:"
def chk(c,msg):
 if not c:raise ValueError(msg)
def hashed_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for part in iter(lambda:f.read(8*1024*1024),b""):h.update(part)
 return h.hexdigest()
def inspect(conn):
 index_bytes=(D/"PACKET_INDEX.csv").read_bytes()
 r=list(csv.DictReader(index_bytes.decode("utf-8-sig").splitlines()))
 chk(len(r)==42,"Original packet index has wrong row count")
 seen=set();checked=[]
 for row in r:
  case=int(row["case_id"]);arm=row["arm"];ident=(case,arm)
  chk(arm in "OWP" and ident not in seen,"Duplicate/invalid arm")
  seen.add(ident)
  p=D/row["filename"]
  chk(p.name==f"CASE_{case:05d}_{arm}.zip","Unexpected packet name")
  chk(p.is_file() and p.stat().st_size==int(row["bytes"]),"Original ZIP missing or wrong size")
  sha=hashed_file(p)
  chk(sha==row["sha256"],"Original ZIP SHA256 disagrees: "+p.name)
  packet_kind=row["source_type"]
  chk(packet_kind in ("FULL_FROZEN_SNAPSHOT","FILTERED_SOURCE_PROVISIONAL"),"Unknown source type")
  original=conn.execute("SELECT original_result_zlib,result_sha256,source_snapshot_type FROM arno_rq3_owp14_run_scans WHERE case_id=? AND arm=?",(case,arm)).fetchone()
  linkage=0
  if original is not None:
   raw=zlib.decompress(original[0])
   chk(hashlib.sha256(raw).hexdigest()==original[1],"Archived result corrupted")
   result=json.loads(raw)
   chk(result.get("frozen_source_sha256")==sha and original[2]==packet_kind,"Packet not linked to original scanner RESULT")
   linkage=1
  checked.append({"case_id":case,"arm":arm,"packet_name":p.name,"bytes":int(row["bytes"]),"sha256":sha,
   "source_type":packet_kind,"historical_issue_text_verified":1 if row["historical_issue_text_verified"]=="True" else 0,
   "baseline_has_historical_rule":1 if row["baseline_has_historical_rule"]=="True" else 0,
   "historical_target_rule":row["target_rule"],"has_exact_original_scan_result_link":linkage})
 chk(len(seen)==42,"Wrong packet identities")
 chk(sum(x["has_exact_original_scan_result_link"] for x in checked)==40,"Unexpected scan-linked cases")
 chk({(x["case_id"],x["arm"]) for x in checked if not x["has_exact_original_scan_result_link"]}=={(8461,"O"),(15151,"O")},"Unexpected uncovered arms")
 chk(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(T,)).fetchone()[0]==0,"Inventory already exists")
 chk(conn.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key=? OR source_key LIKE ?",(INDEX_KEY,KEY_PREFIX+"%")).fetchone()[0]==0,"Sources already indexed")
 return index_bytes,checked
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--apply",action="store_true")
 args=ap.parse_args()
 conn=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=120)
 if not args.apply:conn.execute("PRAGMA query_only=ON")
 conn.execute("PRAGMA foreign_keys=ON")
 try:
  index_bytes,items=inspect(conn)
  summary={"status":"ORIGINAL_OWP14_INPUT_PACKETS_VERIFIED","file_count":42,
   "total_zip_bytes_sha256_verified":sum(x["bytes"] for x in items),
   "scan_linked":sum(x["has_exact_original_scan_result_link"] for x in items),
   "unlinked_original_scan_arms":["CASE_08461_O","CASE_15151_O"],
   "source_types":dict(Counter(x["source_type"] for x in items)),
   "historical_issue_text_verified_true":sum(x["historical_issue_text_verified"] for x in items),
   "archive_not_embedded":True,"source_code_not_extracted":True,
   "generation_executions_inferred":False,
   "packet_index_sha256":hashlib.sha256(index_bytes).hexdigest()}
  report={"summary":summary,"packets":items,"caveats":[
   "Original packet README says input packaging did not automatically run LLM agents.",
   "A packet is an input artifact, not evidence of an original generated patch or full agent trajectory.",
   "All treatment-specific package hashes differ; this does not prove distinct base repository commits.",
   "Filtered source case packets remain provisional and historical issue wording is not verified."]}
  OUT.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   with (OUT/"PREFLIGHT_REPORT.json").open("x") as f:json.dump(report,f,indent=2)
   print(json.dumps(summary,indent=2));return
  conn.execute("BEGIN IMMEDIATE")
  # No rewriting earlier classification, scan or claims tables.
  conn.execute("""INSERT INTO arno_sources (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes)
    VALUES(?,?,?,?,?,?,?,?,?)""",
   (INDEX_KEY,"FROZEN_ORIGINAL_PACKET_INDEX","OWP14 42 generation input packet index",str(D/"PACKET_INDEX.csv"),
    hashlib.sha256(index_bytes).hexdigest(),"csv/utf-8",index_bytes,
    "SHA256_ALL_42_ORIGINAL_INPUT_ZIPS_AND_40_SCAN_LINKS_VERIFIED",
    "Historical issue wording unverified; source snapshots filtered in some cases; input packets are not agent patches."))
  conn.execute("""CREATE TABLE arno_owp14_original_input_packet_inventory_20261029 (
    case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    original_filename TEXT NOT NULL UNIQUE,original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,historical_issue_text_verified INTEGER NOT NULL,
    baseline_has_historical_rule INTEGER NOT NULL,historical_target_rule TEXT,
    has_exact_original_scan_result_link INTEGER NOT NULL CHECK(has_exact_original_scan_result_link IN (0,1)),
    packet_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    packet_index_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),PRIMARY KEY(case_id,arm))""")
  for r in items:
   k=KEY_PREFIX+f'{r["case_id"]:05d}_{r["arm"]}'
   conn.execute("INSERT INTO arno_sources (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)",
   (k,"FROZEN_ORIGINAL_AGENT_INPUT_PACKET",r["packet_name"],str(D/r["packet_name"]),r["sha256"],None,None,
    "ZIP_SHA256_MATCHES_FROZEN_PACKET_INDEX_AND_SCAN_RESULT_WHERE_PRESENT",
    "Private original input ZIP NOT EMBEDDED; do not confuse with original generated patch."))
   conn.execute("INSERT INTO "+T+" VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
    (r["case_id"],r["arm"],r["packet_name"],r["bytes"],r["sha256"],
     r["source_type"],r["historical_issue_text_verified"],r["baseline_has_historical_rule"],
     r["historical_target_rule"],r["has_exact_original_scan_result_link"],k,INDEX_KEY))
  chk(conn.execute("SELECT COUNT(*) FROM "+T).fetchone()[0]==42,"Post-write inventory count")
  chk(not conn.execute("PRAGMA foreign_key_check("+T+")").fetchone(),"New FK mismatch")
  conn.commit()
  with (OUT/"LIVE_REPORT.json").open("x") as f:json.dump(report,f,indent=2)
  print(json.dumps({"status":"ORIGINAL_42_INPUT_PACKET_SOURCES_REGISTERED",**summary},indent=2))
 finally:conn.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("ORIGINAL_PACKET_AUDIT_FAILED: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
