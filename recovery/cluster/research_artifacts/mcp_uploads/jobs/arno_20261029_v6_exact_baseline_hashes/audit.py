#!/usr/bin/env python3
"""Exact O/W/P baseline hash and frozen source identity crosswalk; read-only.
Compares each original RESULT.json digest with 28 verified Screen65 before-SARIF.
Never exports SARIF text, code, prompts, credentials or private source files.
"""
import sqlite3,zlib,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
R=Path.home()/"research_artifacts";DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_20261029_v6_exact_baseline_hashes/REPORT.json"
def h(v):return hashlib.sha256(v).hexdigest()
def expect(ok,msg):
 if not ok:raise ValueError(msg)
con=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
con.execute("PRAGMA query_only=ON")
scr=con.execute("SELECT case_id,wave,sha256 FROM arno_screen65_before_sarif_candidates_20261029").fetchall()
scan=con.execute("""SELECT case_id,arm,original_result_path,result_sha256,original_result_zlib,
source_snapshot_type,codeql_version FROM arno_rq3_owp14_run_scans ORDER BY case_id,arm""").fetchall()
expect(len(scr)==28 and len(scan)==40,"Source row cardinality")
old=defaultdict(dict)
for case,wave,sha in scr:old[case][wave]=sha
per=defaultdict(list)
for case,arm,path,result_sha,blob,snapshot,version in scan:
 raw=zlib.decompress(blob)
 expect(h(raw)==result_sha,"Original result corrupted "+path)
 doc=json.loads(raw)
 baseline=doc.get("baseline_sarif_sha256")
 source=doc.get("frozen_source_sha256")
 expect(isinstance(baseline,str) and len(baseline)==64,"No baseline hash "+path)
 expect(isinstance(source,str) and len(source)==64,"No frozen source hash "+path)
 first=baseline==old[case]["SCREEN65_FIRST"]
 second=baseline==old[case]["SCREEN65_SECOND"]
 per[case].append({"arm":arm,"snapshot":snapshot,"result_sha256":result_sha,
  "baseline_sha256":baseline,"frozen_source_sha256":source,
  "matches_screen65_first_before":first,"matches_screen65_second_before":second,
  "scan_version":version,"reported_current_codeql_version":doc.get("current_codeql_version"),
  "reported_archived_baseline_codeql_version":doc.get("archived_baseline_codeql_version"),
  "reported_suite":doc.get("suite"),"reported_baseline_mode":doc.get("baseline_mode"),
  "reported_source_type":doc.get("source_type")})
cases=[]
for case,rows in sorted(per.items()):
 old_hashes=set(old[case].values())
 bset={x["baseline_sha256"] for x in rows}
 sset={x["frozen_source_sha256"] for x in rows}
 cases.append({"case_id":case,"present_arms":sorted(x["arm"] for x in rows),
  "arms":rows,"baseline_unique_hash_count":len(bset),"frozen_source_unique_hash_count":len(sset),
  "all_arm_baseline_hashes_identical":len(bset)==1,"all_arm_frozen_source_hashes_identical":len(sset)==1,
  "arms_matching_screen65_before":sum(x["baseline_sha256"] in old_hashes for x in rows),
  "arms_matching_first_before":sum(x["matches_screen65_first_before"] for x in rows),
  "arms_matching_second_before":sum(x["matches_screen65_second_before"] for x in rows),
  "baseline_hash_status":"EXACT_MATCH_TO_ARCHIVED_SCREEN65_BEFORE" if all(x["baseline_sha256"] in old_hashes for x in rows) else "NO_EXACT_SCREEN65_BEFORE_MATCH_FOR_SOME_ARMS",
  "baseline_source_commit_equivalence":"NOT_ESTABLISHED_BY_HASH_MATCH_ALONE"})
flat=[x for c in cases for x in c["arms"]]
summary={"cases":len(cases),"total_arms":len(flat),"O_arms":sum(x["arm"]=="O" for x in flat),
 "W_arms":sum(x["arm"]=="W" for x in flat),"P_arms":sum(x["arm"]=="P" for x in flat),
 "arms_matching_first_screen65_before":sum(x["matches_screen65_first_before"] for x in flat),
 "arms_matching_second_screen65_before":sum(x["matches_screen65_second_before"] for x in flat),
 "cases_same_baseline_hash_across_available_arms":sum(c["all_arm_baseline_hashes_identical"] for c in cases),
 "cases_same_frozen_source_hash_across_available_arms":sum(c["all_arm_frozen_source_hashes_identical"] for c in cases),
 "cases_with_no_arm_baseline_exact_match":sum(c["arms_matching_screen65_before"]==0 for c in cases),
 "source_snapshot_types":dict(Counter(x["snapshot"] for x in flat)),
 "suite_values":sorted(set(str(x["reported_suite"]) for x in flat)),
 "baseline_modes":sorted(set(str(x["reported_baseline_mode"]) for x in flat))}
report={"status":"ORIGINAL_OWP14_BASELINE_HASH_CROSSWALK_COMPLETE","summary":summary,"per_case":cases,
 "evidence":"Original frozen RESULT.json SHA256 verified per arm; original 28 Screen65 before SARIF source digests in master.",
 "interpretation_guard":"An exact baseline SARIF SHA256 match establishes identical SARIF bytes, not necessarily direct proof that patch generation was conducted against the identical repository state.",
 "limitations":["Two missing original O-arm patches are NOT reconstructed by a baseline hash match.","Full trajectory and functional correctness not established by scanner metadata.","No original source or prompts written into this report."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":report["status"],"summary":summary,"case_summary":[{k:c[k] for k in ["case_id","present_arms","all_arm_baseline_hashes_identical","all_arm_frozen_source_hashes_identical","arms_matching_first_before","arms_matching_second_before"]} for c in cases],"path":str(OUT)},indent=2))
