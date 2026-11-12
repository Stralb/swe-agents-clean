#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import csv,json
ROOT=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"
CASES=["03429","03581","08152","12344","31207","32759"]
report={"status":"SCANS_COMPLETE_FUNCTIONAL_UNVERIFIED","method":"Frozen baseline CodeQL javascript-security-extended; rule/path/message line-agnostic multiset delta",
 "generated_utc":datetime.now(timezone.utc).isoformat(),"pilot_case_22223_excluded":True,"cases":[],
 "limitations":["CodeQL warning is not proof of an exploitable vulnerability or its absence.",
  "No full functional acceptance tests for these six cases are claimed.",
  "Single generation per condition; descriptive comparisons are not causal evidence.",
  "Filtered/provisional source snapshots for 03429, 12344 and 31207.",
  "Some agent receipts describe partial or otherwise unverified implementations."]}
for c in CASES:
 row={"case":c,"arms":{}}
 for arm in ["A","C"]:
  a=ROOT/"retry_v2"/"results"/("CASE_"+c)/arm/"RESULT.json"
  b=ROOT/("solo_"+c+"_"+arm)/"results"/("CASE_"+c)/arm/"RESULT.json"
  matches=[p for p in [a,b] if p.exists()]
  assert len(matches)==1,(c,arm,[str(x) for x in matches])
  rec=json.loads(matches[0].read_text())
  assert rec["status"]=="CODEQL_SCAN_COMPLETE",(c,arm,rec["status"])
  row["source_kind"]=rec["source_kind"]
  row["baseline_total"]=rec["baseline_total"]
  row["historical_p1_new"]=rec["historical_p1_new"]
  row["historical_p1_total"]=rec["historical_p1_total"]
  wanted=["run_id","receipt_generation_status","patch_sha256","receipt_sha256","after_total",
   "new_conservative_line_agnostic","new_by_rule","newly_absent_p1_warning_count",
   "previous_p1_warning_matches_remaining","after_sarif_sha256"]
  row["arms"][arm]={key:rec[key] for key in wanted}
  row["arms"][arm]["result_path"]=str(matches[0].relative_to(ROOT))
  row["arms"][arm]["functional_tested"]=False
 report["cases"].append(row)
report["counts"]={"case_count":6,"patch_count":12,"historical_p1_new_total":sum(x["historical_p1_new"] for x in report["cases"]),
 "A_new_total":sum(x["arms"]["A"]["new_conservative_line_agnostic"] for x in report["cases"]),
 "C_new_total":sum(x["arms"]["C"]["new_conservative_line_agnostic"] for x in report["cases"]),
 "A_zero_warning_cases":sum(x["arms"]["A"]["new_conservative_line_agnostic"]==0 for x in report["cases"]),
 "C_zero_warning_cases":sum(x["arms"]["C"]["new_conservative_line_agnostic"]==0 for x in report["cases"])}
dest=ROOT/"FINAL_AC6_CODEQL_REPORT.json"
assert not dest.exists()
dest.write_text(json.dumps(report,indent=2))
with (ROOT/"FINAL_AC6_CODEQL_REPORT.csv").open("x",newline="") as f:
 w=csv.writer(f)
 w.writerow(["case","source_kind","baseline_total","P1_total","P1_new","A_total","A_new","A_P1_new_remaining","C_total","C_new","C_P1_new_remaining","A_generation_status","C_generation_status"])
 for x in report["cases"]:
  a=x["arms"]["A"];c=x["arms"]["C"]
  w.writerow([x["case"],x["source_kind"],x["baseline_total"],x["historical_p1_total"],x["historical_p1_new"],a["after_total"],a["new_conservative_line_agnostic"],a["previous_p1_warning_matches_remaining"],c["after_total"],c["new_conservative_line_agnostic"],c["previous_p1_warning_matches_remaining"],a["receipt_generation_status"],c["receipt_generation_status"]])
print(json.dumps({"status":report["status"],"counts":report["counts"]}),flush=True)
