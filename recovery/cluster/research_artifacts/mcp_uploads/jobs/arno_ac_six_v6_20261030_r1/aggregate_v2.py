#!/usr/bin/env python3
"""Evidence-preserving aggregation of the 12 already-complete CodeQL scans (no rescan)."""
from pathlib import Path
from datetime import datetime, timezone
import csv,hashlib,json,zipfile
R=Path.home()/"research_artifacts"
ROOT=R/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
SOURCE=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
MANIFEST=json.loads((SOURCE/"MANIFEST.json").read_text())
CASES=["03429","03581","08152","12344","31207","32759"]
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def where(case,arm):
 if case=="03429" or (case=="08152" and arm=="A"):
  return ROOT/"retry_v2/results"/("CASE_"+case)/arm
 return ROOT/("solo_"+case+"_"+arm)/"results"/("CASE_"+case)/arm
rows=[]
report={"protocol":"A retrospective mechanism guidance; C prospective risk prediction then fresh build",
 "status":"COMPLETE_STATIC_ANALYSIS_ONLY","created_utc":datetime.now(timezone.utc).isoformat(),
 "scanner_suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
 "count_method":"Line-agnostic multiset of (CodeQL rule, relative file path, normalized message)",
 "cases":[],"limitations":["CodeQL findings are not established vulnerabilities.","No issue-acceptance or end-to-end functional validation in these six-case scans.","One generation per condition; no causal effect estimate.","03429,12344,31207 use filtered provisional source snapshots.","31207 A and C receipts state partial implementation.","Original P1 warnings no longer detected is not equivalent to proven remediation."]}
output_paths=[]
for case in CASES:
 original=next(v for v in MANIFEST["runs"] if v["case_id"]==case and v["condition"]=="P1")
 base=B/("CASE_"+case)
 p1=P/("CASE_"+case)/original["run_id"]
 baseline=json.loads((base/"RESULT.json").read_text())
 prior=json.loads((p1/"RESULT.json").read_text())
 assert sha(base/"baseline.sarif")==baseline["sarif_sha256"]
 assert sha(p1/"after.sarif")==prior["after_sarif_sha256"]
 item={"case":case,"source_kind":original["source_kind"],"baseline_total":baseline["result_count"],
       "P1_total":prior["after_total"],"P1_new":prior["new_conservative_line_agnostic"],"arms":{}}
 for arm,suffix in [("A","MECHANISM"),("C","PROSPECTIVE_BUILD")]:
  here=where(case,arm)
  data=json.loads((here/"RESULT.json").read_text())
  rid="PILOT"+case+"_"+suffix+"_R1"
  assert data["run_id"]==rid and data["status"]=="CODEQL_SCAN_COMPLETE",(case,arm)
  assert data["baseline_total"]==item["baseline_total"] and data["historical_p1_new"]==item["P1_new"]
  assert all(data["checks"][stage]["exit"]==0 for stage in ["apply_check","apply","database_create","analysis"])
  assert sha(here/"after.sarif")==data["after_sarif_sha256"],(case,arm,"SARIF")
  patch=ROOT/"evidence"/("PATCH_"+rid+".patch")
  receipt=ROOT/"evidence"/("RECEIPT_"+rid+".json")
  assert sha(patch)==data["patch_sha256"] and sha(receipt)==data["receipt_sha256"],(case,arm,"PATCH/RECEIPT")
  record={"run_id":rid,"status":data["status"],"receipt_generation_status":data["receipt_generation_status"],
    "after_total":data["after_total"],"new":data["new_conservative_line_agnostic"],
    "strict_new":data["new_strict_line_including"],
    "previous_P1_warning_signatures_remaining":data["previous_p1_warning_matches_remaining"],
    "previous_P1_warning_signatures_absent":data["newly_absent_p1_warning_count"],
    "new_by_rule":data["new_by_rule"],"patch_sha256":data["patch_sha256"],
    "sarif_sha256":data["after_sarif_sha256"],"result_relative_path":str((here/"RESULT.json").relative_to(ROOT)),
    "sarif_relative_path":str((here/"after.sarif").relative_to(ROOT)),
    "functional_status":"NOT_VERIFIED"}
  item["arms"][arm]=record
  output_paths.append((here,case,arm))
 rows.append(item)
 report["cases"].append(item)
counts={"cases":len(rows),"scans":len(output_paths),"P1_new":sum(x["P1_new"] for x in rows)}
for arm in ["A","C"]:
 counts[arm+"_new"]=sum(x["arms"][arm]["new"] for x in rows)
 counts[arm+"_zero_new"]=sum(x["arms"][arm]["new"]==0 for x in rows)
 counts[arm+"_P1_signatures_absent"]=sum(x["arms"][arm]["previous_P1_warning_signatures_absent"] for x in rows)
report["counts"]=counts
assert counts["scans"]==12
j=ROOT/"FINAL_AC6_CODEQL_REPORT_V2.json";c=ROOT/"FINAL_AC6_CODEQL_REPORT_V2.csv";zpath=ROOT/"FINAL_AC6_EVIDENCE_COMPACT_V2.zip"
for p in [j,c,zpath]:assert not p.exists(),p
j.write_text(json.dumps(report,indent=2)+"\n")
with c.open("x",newline="") as f:
 w=csv.writer(f)
 w.writerow(["case","source_kind","baseline_total","P1_total","P1_new",
  "A_total","A_new","A_P1_remaining","C_total","C_new","C_P1_remaining","A_receipt_status","C_receipt_status"])
 for t in rows:
  a=t["arms"]["A"];d=t["arms"]["C"]
  w.writerow([t["case"],t["source_kind"],t["baseline_total"],t["P1_total"],t["P1_new"],
    a["after_total"],a["new"],a["previous_P1_warning_signatures_remaining"],
    d["after_total"],d["new"],d["previous_P1_warning_signatures_remaining"],
    a["receipt_generation_status"],d["receipt_generation_status"]])
with zipfile.ZipFile(zpath,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in [j,c]:z.write(p,p.name)
 archive=ROOT/"evidence"/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"
 z.write(archive,"original_agent_evidence/"+archive.name)
 for here,case,arm in output_paths:
  for fn in ["RESULT.json","WARNING_TRACE.json","apply.log","apply_check.log"]:
   z.write(here/fn,"scans/CASE_"+case+"/"+arm+"/"+fn)
 for case in CASES:
  original=next(v for v in MANIFEST["runs"] if v["case_id"]==case and v["condition"]=="P1")
  b=B/("CASE_"+case)/"RESULT.json"
  p=P/("CASE_"+case)/original["run_id"]/"RESULT.json"
  z.write(b,"baselines/CASE_"+case+"/RESULT.json")
  z.write(p,"historical_P1/CASE_"+case+"/RESULT.json")
 z.writestr("README.txt",
  "Original 12 patches, 12 receipts and 6 risks are inside original_agent_evidence ZIP.\n"
  "Raw SARIF remains on Wits cluster and has SHA-256/path in summary JSON; no SARIF is included in this compact package.\n"
  "Scanner findings != proven vulnerabilities. Functional testing remains separate.\n")
with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
print(json.dumps({"status":"AGGREGATED","counts":counts,"report_sha256":sha(j),
  "zip_sha256":sha(zpath),"zip_bytes":zpath.stat().st_size}),flush=True)
