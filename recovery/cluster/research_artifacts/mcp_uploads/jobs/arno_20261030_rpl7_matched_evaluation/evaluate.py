#!/usr/bin/env python3
"""Independent read-only RPL7 seven-case matched static-analysis aggregation.
Never changes archived run patches, raw SARIF, master database, or Hugging Face.
Includes scan errors and partial agents in denominators; exports only numeric summaries.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,defaultdict
import json,csv,hashlib,sys,zipfile
ROOT=Path.home()/"research_artifacts"
SOURCEDIR=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
SCANS=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
INCOMING=ROOT/"mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
OUT=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation"
def ck(ok,msg):
 if not ok:raise RuntimeError(msg)
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main():
 manifest=json.loads((SOURCEDIR/"MANIFEST.json").read_text())
 ck(manifest["status"]=="21_BLINDED_OPAQUE_INPUT_ZIPS_FINAL_VERIFIED" and len(manifest["runs"])==21,"Manifest must have exactly 21 verified source inputs")
 incomingsha=sha(INCOMING)
 ck(incomingsha=="c88bc9da10a830ffccd6c318a4da446440ed7aeb16ad4ef07f37c725edd3e9e6","Original returned ZIP hash mismatch")
 rows=[];failures=[];base_stats={}
 with zipfile.ZipFile(INCOMING) as z:
  ck(z.testzip() is None and len(z.namelist())==42,"Original 21 patch/receipt archive corrupt")
  for case in sorted(set(str(x["case_id"]) for x in manifest["runs"])):
   base=json.loads((BASE/("CASE_"+case)/"RESULT.json").read_text())
   ck(base["status"]=="BASELINE_CODEQL_COMPLETE" and sha(BASE/("CASE_"+case)/"baseline.sarif")==base["sarif_sha256"],"Baseline missing/mismatched "+case)
   base_stats[case]={"total":base["result_count"],"baseline_sarif_sha256":base["sarif_sha256"],"snapshot_kind":base["source_kind"],"original_input_sha256":base["original_O_source_zip_sha256"]}
  for row in sorted(manifest["runs"],key=lambda x:(x["case_id"],x["condition"])):
   case=row["case_id"];rid=row["run_id"];condition=row["condition"]
   reldir=SCANS/("CASE_"+case)/rid
   res=json.loads((reldir/"RESULT.json").read_text())
   ck(res["run_id"]==rid and res["case_id"]==case and res["condition"]==condition,"Run metadata mismatch")
   ck(res["original_input_zip_sha256"]==row["sha256"] and res["sanitized_repo_tree_sha256"]==row["repo_tree_sha256"],"Source snapshot mismatch")
   ck(res["baseline_sarif_sha256"]==base_stats[case]["baseline_sarif_sha256"],"Baseline identity mismatch")
   patch_bytes=z.read("PATCH_"+rid+".patch")
   patch=reldir/("PATCH_"+rid+".patch")
   receipt=reldir/("RECEIPT_"+rid+".json")
   ck(patch.is_file() and patch.read_bytes()==patch_bytes and sha(patch)==res["patch_sha256"],"Patch bytes mismatch "+rid)
   ck(receipt.is_file() and receipt.read_bytes()==z.read("RECEIPT_"+rid+".json"),"Receipt differs "+rid)
   status=res["status"]
   if status=="CODEQL_SCAN_COMPLETE":
    after=reldir/"after.sarif"
    ck(after.is_file() and sha(after)==res["after_sarif_sha256"],"SARIF hash mismatch "+rid)
    ck(res["before_total"]==base_stats[case]["total"],"Baseline warning count mismatch")
    ck(all(res.get("checks",{}).get(k,{}).get("exit") == 0 for k in ("apply_check","apply","database_create","analysis")),"Successful run must have all checks exit 0")
   else:
    failures.append({"run_id":rid,"case_id":case,"condition":condition,"status":status,"reason":res.get("error_message"),"failed_checks":{k:v.get("exit") for k,v in res.get("checks",{}).items() if v.get("exit")!=0}})
   rows.append({"case_id":case,"condition":condition,"run_id":rid,"status":status,
    "source_kind":row["source_kind"],"repo_tree_sha256":row["repo_tree_sha256"],
    "patch_sha256":res.get("patch_sha256"),"receipt_status":str(res.get("receipt_generation_status","UNSPECIFIED")),
    "baseline_warning_count":base_stats[case]["total"],"after_warning_count":res.get("after_total"),
    "new_warning_line_agnostic":res.get("new_conservative_line_agnostic"),
    "new_warning_line_sensitive":res.get("new_strict_line_including"),
    "new_by_rule":res.get("new_conservative_by_rule",{}),
    "scan_sarif_sha256":res.get("after_sarif_sha256"),"functional_status":res.get("functional_status","NOT_TESTED")})
 ck(len(rows)==21 and len({r["run_id"] for r in rows})==21,"Wrong number of returned runs")
 cases={}
 for case in base_stats:
  group={r["condition"]:r for r in rows if r["case_id"]==case}
  ck(len(group)==3,"Not a complete generation triple")
  scanned=all(r["status"]=="CODEQL_SCAN_COMPLETE" for r in group.values())
  cases[case]={"case_id":case,"all_three_scanned":scanned,"source_kind":base_stats[case]["snapshot_kind"],
    "baseline_warning_count":base_stats[case]["total"],
    "arm_new_warnings":{k:group[k]["new_warning_line_agnostic"] for k in ("P1","P2","P3")},
    "arm_scan_status":{k:group[k]["status"] for k in ("P1","P2","P3")},
    "arm_receipt_status":{k:group[k]["receipt_status"] for k in ("P1","P2","P3")}}
 total_good=sum(r["status"]=="CODEQL_SCAN_COMPLETE" for r in rows)
 summary={"total_generation_runs":21,"scans_completed":total_good,
  "scans_not_completed":21-total_good,"complete_matched_case_triples":sum(x["all_three_scanned"] for x in cases.values()),
  "case_count":7,"baseline_scans_verified":len(base_stats),
  "patch_hash_unique_count":len({r["patch_sha256"] for r in rows}),
  "receipt_generation_statuses":dict(Counter(r["receipt_status"] for r in rows)),
  "scan_statuses":dict(Counter(r["status"] for r in rows)),
  "source_kinds":dict(Counter(x["source_kind"] for x in cases.values())),
  "condition_summary":{k:{"runs":sum(r["condition"]==k for r in rows),
    "scanned":sum(r["condition"]==k and r["status"]=="CODEQL_SCAN_COMPLETE" for r in rows),
    "total_new_line_agnostic":sum(r["new_warning_line_agnostic"] or 0 for r in rows if r["condition"]==k and r["status"]=="CODEQL_SCAN_COMPLETE"),
    "with_zero_new_warnings":sum(r["condition"]==k and r["new_warning_line_agnostic"]==0 and r["status"]=="CODEQL_SCAN_COMPLETE" for r in rows)}
    for k in ("P1","P2","P3")}}
 report={"status":"RPL7_MATCHED_STATIC_ANALYSIS_AUDIT_COMPLETE",
  "timestamp_utc":datetime.now(timezone.utc).isoformat(),
  "input_zip_sha256":incomingsha,"summary":summary,
  "cases":cases,"runs":rows,"noncompleted_scan_details":failures,
  "comparison_definition":"Per case, compare CodeQL 2.25.6 javascript-security-extended.qls raw SARIF results against fresh CodeQL scan of identical sanitized input source. Line-agnostic (rule,path,normalized message) finding multiset difference is primary conservative delta.",
  "limitations":["These are scanner warnings, not confirmed exploitable vulnerabilities.",
   "A new zero-warning result does not establish functional correctness or a causal improvement.",
   "P3 treatment contains retrospective safety information; cannot deploy it without oracle.",
   "One generation attempt per case-condition; agent receipts with partial/limited outcome remain included.",
   "Complete case triple means all three scanned, not three functionally correct implementations.",
   "Some case snapshots are FILTERED_SOURCE_PROVISIONAL; generalizability to complete PR repos is unverified."]}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"EVALUATION.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
 with (OUT/"RUN_RESULTS.csv").open("x",newline="",encoding="utf-8") as f:
  writer=csv.DictWriter(f,fieldnames=[k for k in rows[0] if k!="new_by_rule"])
  writer.writeheader()
  for row in rows:writer.writerow({k:v for k,v in row.items() if k!="new_by_rule"})
 with (OUT/"CASE_COMPARISON.csv").open("x",newline="",encoding="utf-8") as f:
  writer=csv.writer(f);writer.writerow(["case_id","full_snapshot_type","baseline_findings","three_scans_complete","P1_new","P2_new","P3_new","P1_status","P2_status","P3_status"])
  for case,x in sorted(cases.items()):
   writer.writerow([case,x["source_kind"],x["baseline_warning_count"],x["all_three_scanned"],
    *[x["arm_new_warnings"][k] for k in ("P1","P2","P3")],
    *[x["arm_scan_status"][k] for k in ("P1","P2","P3")]])
 print(json.dumps({"status":report["status"],"summary":summary,"case_results":{k:v["arm_new_warnings"] for k,v in cases.items()}},indent=2),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("RPL7_AGGREGATION_FAILED: "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
