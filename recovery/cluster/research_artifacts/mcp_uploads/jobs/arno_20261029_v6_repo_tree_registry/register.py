#!/usr/bin/env python3
"""Append-only repository equivalence provenance for OWP14 input packets.
Uses independently verified read-only ZIP audit; never changes archived inputs.
"""
import argparse,sqlite3,json,hashlib,sys
from pathlib import Path
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SRC=R/"mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/REPORT.json"
DIR=R/"mcp_uploads/jobs/arno_20261029_v6_repo_tree_registry"
TABLE="arno_owp14_input_repo_equivalence_20261029"
SOURCE_KEY="owp14_42_input_repo_tree_equivalence_20261029"
def check(ok,msg):
 if not ok:raise RuntimeError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument("--apply",action="store_true");args=p.parse_args()
 raw=SRC.read_bytes();doc=json.loads(raw)
 check(doc["status"]=="REPO_TREE_INPUT_EQUALITY_AUDIT_COMPLETE","Wrong source audit")
 check(doc["summary"]["cases"]==14 and doc["summary"]["arms"]==42 and doc["summary"]["identical_repository_content_cases"]==14,"Not all repository inputs identical")
 check(doc["summary"]["cases_with_issue_in_all_arms"]==14,"Missing original issue text in input")
 check(doc["summary"]["issue_distinct_hash_count_distribution"]=={"3":14},"Not all three issue treatments distinct")
 rows=doc["per_case"]
 check(len(rows)==14 and len({x["case_id"] for x in rows})==14,"Duplicate cases")
 con=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=90)
 try:
  con.execute("PRAGMA foreign_keys=ON")
  if not args.apply:con.execute("PRAGMA query_only=ON")
  check(con.execute("SELECT COUNT(*) FROM arno_owp14_original_input_packet_inventory_20261029").fetchone()[0]==42,"Original packet registry missing")
  check(con.execute("SELECT COUNT(*) FROM arno_experiment_runs").fetchone()[0]==40,"Original scan arms missing")
  check(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()[0]==0,"Equivalence table exists")
  check(con.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key=?",(SOURCE_KEY,)).fetchone()[0]==0,"Audit source already exists")
  for x in rows:
   check(x["same_repo_tree_contents_all_arms"],"Non-equivalent source in "+str(x["case_id"]))
   check(x["distinct_issue_file_hashes"]==3,"Not three different ISSUE.md texts")
   check(len(x["source_tree_sha256"])==64,"Incomplete repo fingerprint")
   check(con.execute("SELECT COUNT(*) FROM arno_owp14_original_input_packet_inventory_20261029 WHERE case_id=?",(x["case_id"],)).fetchone()[0]==3,"Original packet arms missing")
  d={"status":"INPUT_REPO_EQUIVALENCE_PREFLIGHT_PASS","cases":14,"arms":42,
    "all_repo_trees_identical_within_cases":True,"all_issue_texts_distinct_within_cases":True,
    "source_report_sha256":hashlib.sha256(raw).hexdigest(),"historical_commit_proven":False,
    "historical_issue_text_verified":False,"master_modified":bool(args.apply)}
  DIR.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   with (DIR/"PREFLIGHT.json").open("x") as f:json.dump(d,f,indent=2)
   print(json.dumps(d,indent=2));return
  check((DIR/"PREFLIGHT.json").is_file(),"Preflight report missing")
  con.execute("BEGIN IMMEDIATE")
  con.execute("INSERT INTO arno_sources (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)",
    (SOURCE_KEY,"DERIVED_VERIFIED_EXPERIMENT_INPUT_EQUIVALENCE","O/W/P 14-case repo file tree equality verification",str(SRC),hashlib.sha256(raw).hexdigest(),
     "json/utf-8",raw,"14_CASES_42_PACKET_REPOSITORY_FILE_TREES_IDENTICAL_ISSUE_MD_DIFFERENT",
     "Derived hashing audit; original input ZIP source hashes separately verified. Does not prove historical Git commits or actual agent-execution compliance."))
  con.execute("""CREATE TABLE arno_owp14_input_repo_equivalence_20261029 (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    repo_tree_sha256 TEXT NOT NULL,repo_member_count INTEGER NOT NULL,
    repo_total_bytes INTEGER NOT NULL,source_packet_arms INTEGER NOT NULL,
    distinct_issue_md_hashes INTEGER NOT NULL,
    input_equivalence_status TEXT NOT NULL,
    historical_pr_revision_status TEXT NOT NULL,
    historical_issue_wording_status TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
  )""")
  for x in rows:
   con.execute("INSERT INTO "+TABLE+" VALUES(?,?,?,?,?,?,?,?,?,?)",
    (x["case_id"],x["source_tree_sha256"],x["repo_files_by_arm"]["O"],
     x["repo_bytes_by_arm"]["O"],3,x["distinct_issue_file_hashes"],
     "ALL_THREE_PACKET_REPO_TREES_IDENTICAL_BY_MEMBER_AND_CONTENT",
     "NOT_VERIFIED","NOT_VERIFIED",SOURCE_KEY))
  check(con.execute("SELECT COUNT(*) FROM "+TABLE).fetchone()[0]==14,"Insert count mismatch")
  check(not con.execute("PRAGMA foreign_key_check("+TABLE+")").fetchone(),"New inventory FK mismatch")
  con.commit()
  with (DIR/"LIVE_REPORT.json").open("x") as f:json.dump(d,f,indent=2)
  print(json.dumps({"status":"INPUT_REPO_EQUIVALENCE_APPENDED","cases":14,"sha256":hashlib.sha256(raw).hexdigest(),"old_tables_changed":False},indent=2))
 finally:con.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("REPO_EQUIVALENCE_INDEX_ERROR: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
