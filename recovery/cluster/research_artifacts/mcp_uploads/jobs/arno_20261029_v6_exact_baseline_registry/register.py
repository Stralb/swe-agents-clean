#!/usr/bin/env python3
"""Append-only original OWP14 scan-to-baseline SHA256 lineage, no raw ZIP contents or SARIF copied."""
from pathlib import Path
import sqlite3,json,hashlib,argparse,sys
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
REPORT=R/"mcp_uploads/jobs/arno_20261029_v6_exact_baseline_hashes/REPORT.json"
OUT=R/"mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry"
TABLE="arno_owp14_exact_scan_baseline_links_20261029"
SOURCE_KEY="owp14_exact_baseline_sha_crosswalk_20261029"
def req(ok,message):
 if not ok:raise RuntimeError(message)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--apply",action="store_true")
 args=ap.parse_args()
 raw=REPORT.read_bytes();rep=json.loads(raw);summary=rep["summary"]
 req(rep["status"]=="ORIGINAL_OWP14_BASELINE_HASH_CROSSWALK_COMPLETE","Wrong source report")
 req(summary["total_arms"]==40 and summary["arms_matching_first_screen65_before"]==40
     and summary["arms_matching_second_screen65_before"]==0
     and summary["cases_same_baseline_hash_across_available_arms"]==14,"Baseline proof incomplete")
 conn=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=120)
 try:
  if not args.apply:conn.execute("PRAGMA query_only=ON")
  conn.execute("PRAGMA foreign_keys=ON")
  req(conn.execute("SELECT count(*) FROM sqlite_master WHERE name=? AND type='table'",(TABLE,)).fetchone()[0]==0,"Baseline link table already exists")
  req(conn.execute("SELECT count(*) FROM arno_sources WHERE source_key=?",(SOURCE_KEY,)).fetchone()[0]==0,"Baseline report source already registered")
  req(conn.execute("SELECT count(*) FROM arno_owp14_original_input_packet_inventory_20261029").fetchone()[0]==42,"Original packet inventory missing")
  req(conn.execute("SELECT count(*) FROM arno_owp14_input_repo_equivalence_20261029").fetchone()[0]==14,"Repo equivalence proof missing")
  rows=[]
  for case in rep["per_case"]:
   case_id=case["case_id"]
   req(case["all_arm_baseline_hashes_identical"],"Within-case baseline hashes differ")
   req(case["arms_matching_first_before"]==len(case["arms"]) and case["arms_matching_second_before"]==0,"Baseline wave mismatch")
   ref=conn.execute("SELECT sha256,zip_member_path FROM arno_screen65_before_sarif_candidates_20261029 WHERE case_id=? AND wave='SCREEN65_FIRST'",(case_id,)).fetchone()
   req(ref is not None,"Missing Screen65 first-wave candidate")
   for arm in case["arms"]:
    a=arm["arm"];sha=arm["baseline_sha256"];src=arm["frozen_source_sha256"]
    req(sha==ref[0] and arm["matches_screen65_first_before"] and not arm["matches_screen65_second_before"],"Exact SARIF hash mismatch")
    result=conn.execute("SELECT result_sha256,source_snapshot_type,codeql_version FROM arno_rq3_owp14_run_scans WHERE case_id=? AND arm=?",(case_id,a)).fetchone()
    pkt=conn.execute("SELECT sha256,source_type FROM arno_owp14_original_input_packet_inventory_20261029 WHERE case_id=? AND arm=?",(case_id,a)).fetchone()
    req(result is not None and pkt is not None,"Original arm/source absent")
    req(result[0]==arm["result_sha256"] and result[1]==arm["snapshot"] and result[2]==arm["scan_version"],"Original scan metadata disagrees")
    req(src==pkt[0] and result[1]==pkt[1],"Input ZIP source digest mismatch")
    req(arm["reported_suite"]=="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls","Unexpected CodeQL suite")
    rows.append((case_id,a,sha,src,ref[1],arm["scan_version"],arm["snapshot"],SOURCE_KEY))
  req(len(rows)==40 and len({(x[0],x[1]) for x in rows})==40,"Wrong linked rows")
  summary_out={"status":"OWP14_EXACT_BASELINE_LINKS_VERIFIED","linked_original_scans":40,
   "first_wave_byte_exact_baseline_matches":40,"source_input_zip_hash_matches":40,
   "same_input_repo_tree_per_case":14,"historical_git_commit_equivalence_proven":False,
   "historical_issue_wording_verified":False,
   "full_agent_execution_proven":False,
   "frozen_evidence_modified":False}
  OUT.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   with (OUT/"PREFLIGHT.json").open("x") as f:json.dump(summary_out,f,indent=2)
   print(json.dumps(summary_out,indent=2));return
  req((OUT/"PREFLIGHT.json").is_file(),"No completed preflight report")
  conn.execute("BEGIN IMMEDIATE")
  conn.execute("INSERT INTO arno_sources (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)",
  (SOURCE_KEY,"VERIFIED_DERIVED_BASELINE_CROSSWALK","OWP14 archived scan to Screen65 first baseline exact SHA256 matches",
   str(REPORT),hashlib.sha256(raw).hexdigest(),"json/utf-8",raw,
   "40_RESULT_BASELINE_SHA256_TO_SCREEN65_FIRST_AND_40_FROZEN_INPUT_ZIP_SHA256",
   "Baseline matching is exact SARIF bytes and packet identity, not independent proof of historical PR-time Git revisions or functional equivalence."))
  conn.execute("""CREATE TABLE arno_owp14_exact_scan_baseline_links_20261029 (
    case_id INTEGER NOT NULL,arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    baseline_sarif_sha256 TEXT NOT NULL,original_input_packet_sha256 TEXT NOT NULL,
    screen65_first_before_member_path TEXT NOT NULL,
    codeql_version TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,
    exact_match_status TEXT NOT NULL DEFAULT 'BYTE_IDENTICAL_FIRST_WAVE_SARIF_AND_PACKET_SHA',
    historical_pr_revision_equivalence TEXT NOT NULL DEFAULT 'NOT_VERIFIED',
    original_report_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES arno_rq3_owp14_run_scans(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES arno_owp14_original_input_packet_inventory_20261029(case_id,arm),
    FOREIGN KEY(case_id) REFERENCES cases(id)
  )""")
  conn.executemany("""INSERT INTO arno_owp14_exact_scan_baseline_links_20261029
    (case_id,arm,baseline_sarif_sha256,original_input_packet_sha256,screen65_first_before_member_path,
     codeql_version,source_snapshot_type,original_report_source_key) VALUES(?,?,?,?,?,?,?,?)""",rows)
  req(conn.execute("SELECT COUNT(*) FROM "+TABLE).fetchone()[0]==40,"Post-import count mismatch")
  req(not conn.execute("PRAGMA foreign_key_check("+TABLE+")").fetchone(),"Baseline-link FK integrity failed")
  conn.commit()
  summary_out["status"]="OWP14_EXACT_BASELINE_LINKS_APPENDED"
  with (OUT/"LIVE_REPORT.json").open("x") as f:json.dump(summary_out,f,indent=2)
  print(json.dumps(summary_out,indent=2))
 finally:conn.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("BASELINE_LINK_REGISTER_FAILED: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
