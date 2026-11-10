#!/usr/bin/env python3
"""Read-only final analysis of pilot A/B/C against same original case 22223 baseline.
Does not import into master DB or claim functional correctness.
"""
from pathlib import Path
import json,csv,hashlib
ROOT=Path.home()/"research_artifacts"
D=ROOT/"mcp_uploads/jobs/arno_20261030_case22223_three_pilot_scan"
RESULTS=D/"results"
old=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_22223"
baseline=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_22223"
source=ROOT/"mcp_uploads/arno_20261030_case22223_three_pilot_intake/ARNO_22223_THREE_PILOT_OUTPUTS_FOR_WITS_20261030.zip"
new=[json.loads((RESULTS/x/"RESULT.json").read_text()) for x in "ABC"]
assert len(new)==3 and all(r["status"]=="CODEQL_SCAN_COMPLETE" for r in new)
assert len({r["patch_sha256"] for r in new})==3
b=json.loads((baseline/"RESULT.json").read_text())
assert b["result_count"]==41 and b["status"]=="BASELINE_CODEQL_COMPLETE"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)=="59eff1ec445ee38a0d14bc525b9de478e5b29b4867812ec30378093674debafd"
for r in new:
 assert r["baseline_sarif_sha256"]==b["sarif_sha256"]
 assert r["source_zip_sha256"]=="d4e4eac094924b52f16a98593efb7a9770b542150eb9e31de4026f426c7e6f8c"
 assert r["codeql_version"]=="2.25.6"
 assert sha(RESULTS/r["arm"]/"after.sarif")==r["after_sarif_sha256"]
 assert sha(RESULTS/r["arm"]/("PATCH_"+r["run_id"]+".patch"))==r["patch_sha256"]
 assert r["checks"]["apply_check"]["exit"]==0 and r["checks"]["analysis"]["exit"]==0
 # No incorrectly reported green functional results.
 assert r["functional_status"]=="NOT_TESTED"
old_id={"P1":"RPL7_RUN_3D0780CD09D2","P2":"RPL7_RUN_AC9DEC20CA02","P3":"RPL7_RUN_9A4CEC136191"}
old_recs={}
for cond,rid in old_id.items():
 x=json.loads((old/rid/"RESULT.json").read_text())
 assert x["status"]=="CODEQL_SCAN_COMPLETE" and x["before_total"]==41
 old_recs[cond]={"run_id":rid,"introduced_warnings":x["new_conservative_line_agnostic"],
 "warning_rules":x["new_conservative_by_rule"],"receipt_status":x["receipt_generation_status"],
 "sha256":x["after_sarif_sha256"],"functional_status":"NOT_TESTED"}
assert [old_recs[x]["introduced_warnings"] for x in ("P1","P2","P3")]==[3,2,1]
cases={r["arm"]:{"run_id":r["run_id"],"introduced_warnings":r["new_conservative_count"],
 "warning_rules":r["new_conservative_by_rule"],"agent_receipt_status":r["receipt_status"],
 "scan_status":r["status"],"source_kind":"FULL_FROZEN_SNAPSHOT",
 "after_sarif_sha256":r["after_sarif_sha256"],"functional_status":r["functional_status"]} for r in new}
res={"status":"ARNO_22223_THREE_PILOT_CODEQL_AUDIT_COMPLETE","original_case":"22223",
 "baseline_warning_total":41,"new_scan_count":3,"original_comparison":old_recs,
 "pilots":cases,"best_pilot_by_new_warning_count":sorted(cases,key=lambda a:cases[a]["introduced_warnings"]),
 "important_design_note":"A implements original task with retrospectively derived mechanism; B performs blind review then repair of original P1 patch; C predicts risks without hindsight then implements from scratch. Results are descriptive and are not estimates of comparable causal treatment effects.",
 "limitations":["No functional task acceptance test was executed for all arms; CodeQL warnings are not vulnerabilities.",
 "Only one case and one attempt per arm; no significance tests or global claims.",
 "Agent receipt statuses and all intermediate reports retained even if limited.",
 "Old baseline/codeql comparison uses the same original frozen source and CodeQL 2.25.6 suite.",
 "The original input ZIP and returned Stage2 nested ZIPs are archived separately and cryptographically identified."]}
(D/"PILOT_COMPARISON.json").write_text(json.dumps(res,indent=2))
with (D/"PILOT_COMPARISON.csv").open("w",newline="") as f:
 w=csv.writer(f)
 w.writerow(["condition","run_id","new_conservative_warnings","rule_distribution","codeql_state","functional_status"])
 for name,x in old_recs.items():w.writerow([name,x["run_id"],x["introduced_warnings"],json.dumps(x["warning_rules"]),"CODEQL_SCAN_COMPLETE","NOT_TESTED"])
 for name,x in cases.items():w.writerow([name,x["run_id"],x["introduced_warnings"],json.dumps(x["warning_rules"]),x["scan_status"],"NOT_TESTED"])
print(json.dumps({"status":res["status"],"baseline":41,"pilots":cases,
 "original_counts":{a:x["introduced_warnings"] for a,x in old_recs.items()}},indent=2),flush=True)
