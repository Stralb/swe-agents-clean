#!/usr/bin/env python3
"""Run third-iteration CodeQL scans in bounded local parallelism within ONE Slurm allocation.
No repo build or package scripts. Every case gets its own log and immutable result."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import os,sys,subprocess,json,time,traceback,hashlib,csv,zipfile,collections
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
STAGE=ROOT/"screen65_iter3_staged_20261019_v2_bigbatch"
JOB=os.environ["SLURM_JOB_ID"]
OUT=ROOT/("screen65_iter3_codeql_job"+JOB)
OUT.mkdir(parents=True,exist_ok=False)
source=json.loads((STAGE/"MANIFEST.json").read_text())
assert source["status"]=="STAGED" and source["patch_count"]==65 and len(source["patches"])==65
assert source["transfer"]["sha256"]=="f056afba155916915a7fb6613a4a9fa11dc0940f3a4ac5f6deae46359941aee4"
code=Path.home()/"research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/scan65.py"
assert code.is_file()
p=subprocess.run([sys.executable,"-m","py_compile",str(code)],capture_output=True,text=True)
assert p.returncode==0,p.stderr
def worker(i,item):
 env=dict(os.environ)
 env["SLURM_ARRAY_JOB_ID"]=JOB
 env["SLURM_ARRAY_TASK_ID"]=str(i)
 cid=item["case_id"]
 log=OUT/("WORKER_CASE_%05d.log"%cid)
 t=time.monotonic()
 with log.open("w") as f:
  try:
   cp=subprocess.run([sys.executable,str(code)],cwd=OUT,env=env,
    stdout=f,stderr=subprocess.STDOUT,timeout=9200)
   rc=cp.returncode
  except Exception as e:
   rc=124
   f.write("\nRUNNER_EXCEPTION "+repr(e)+"\n")
 return {"case_id":cid,"index":i,"worker_rc":rc,"wall_seconds":round(time.monotonic()-t,1),
         "worker_log":log.name}
tasks={}
with ThreadPoolExecutor(max_workers=3) as ex:
 for idx,item in enumerate(source["patches"]):
  tasks[ex.submit(worker,idx,item)]=item["case_id"]
 for done in as_completed(tasks):
  cid=tasks[done]
  try:
   status=done.result()
  except Exception as e:status={"case_id":cid,"runner_error":repr(e),"worker_rc":127}
  with (OUT/"DRIVER_PROGRESS.jsonl").open("a") as f:f.write(json.dumps(status)+"\n")
  print("ITER3_PROGRESS",status,flush=True)
print("WORKERS_DONE",JOB,flush=True)
# End-of-run complete report. Preserve failures as failures, never impute scanner-negative.
baseline={int(r["case_id"]):r for r in csv.DictReader(
 (ROOT/"screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv").open(newline=""))}
cohort={668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759}
rows=[]
for case in source["patches"]:
 cid=case["case_id"]
 fn=OUT/("CASE_%05d"%cid)/"RESULT.json"
 if fn.is_file():
  res=json.loads(fn.read_text())
 else:
  res={"stage":"MISSING_RESULT","error":"Scanner never wrote a result","source_type":"UNKNOWN"}
 findings=res.get("findings") or {}
 targets=set(x for x in baseline[cid].get("historical_target_rules","").split(";") if x)
 candidates=findings.get("new_strong_findings") or []
 new_on_added=[x for x in candidates if x["on_added_line"]]
 new_target=[x for x in candidates if x["historical_rule_class"]]
 target_added=[x for x in new_target if x["on_added_line"]]
 source_type=res.get("source_type","UNKNOWN")
 newcase=cid not in cohort
 if res["stage"]!="SCAN_COMPLETE":priority="FAILED_SCAN_OR_APPLY"
 elif not newcase:priority="ALREADY_IN_14_REPLICATION"
 elif new_target and target_added and source_type=="FULL_FROZEN_SNAPSHOT":priority="A_HISTORICAL_RULE_ON_ADDED_LINE_FULL"
 elif new_target and source_type=="FULL_FROZEN_SNAPSHOT":priority="B_HISTORICAL_RULE_OTHER_LOCATION_FULL"
 elif candidates and source_type=="FULL_FROZEN_SNAPSHOT" and new_on_added:priority="C_NEW_RULE_ON_ADDED_LINE_FULL"
 elif candidates and source_type=="FULL_FROZEN_SNAPSHOT":priority="D_NEW_RULE_OTHER_LOCATION_FULL"
 elif candidates:priority="E_FILTERED_SOURCE_PROVISIONAL"
 else:priority="NO_NEW_SCANNER_FINDING"
 rows.append({
 "case_id":cid,"cohort":"EXISTING_14" if not newcase else "NEW_51",
 "status":res["stage"],"source_type":source_type,"generation_claim":case["status"],
 "before_alerts":findings.get("before_total"),"after_alerts":findings.get("after_total"),
 "new_strong":findings.get("new_strong_count"),"new_conservative":findings.get("new_weak_count"),
 "new_on_added_line":len(new_on_added),"new_historical_rule":len(new_target),
 "historical_rule_on_added_line":len(target_added),
 "historical_rules":";".join(sorted(targets)),
 "new_rules":";".join(f"{k}:{v}" for k,v in sorted((findings.get("new_by_rule_strong") or {}).items())),
 "candidate_priority":priority,"patch_sha256":case["patch_sha256"],
 "baseline_sha256":res.get("baseline_sarif_sha256"),"source_sha256":res.get("source_archive_sha256"),
 "error":res.get("error","")})
assert len(rows)==65
fields=list(rows[0])
with (OUT/"SCREEN65_ITER3_RESULTS.csv").open("x",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
counter=collections.Counter(x["candidate_priority"] for x in rows)
positive=[x for x in rows if x["new_strong"] and x["status"]=="SCAN_COMPLETE"]
new_positive=[x for x in positive if x["cohort"]=="NEW_51"]
strict=[x for x in new_positive if x["candidate_priority"]=="A_HISTORICAL_RULE_ON_ADDED_LINE_FULL"]
summary={
 "stage":"COMPLETE_WITH_FAILURES_RETAINED" if any(x["status"]!="SCAN_COMPLETE" for x in rows) else "COMPLETE",
 "completed_scans":sum(x["status"]=="SCAN_COMPLETE" for x in rows),
 "failed_scans":sum(x["status"]!="SCAN_COMPLETE" for x in rows),
 "total_uploaded":65,"current_cohort":14,"outside_cohort":51,
 "positive_cases_all":len(positive),"positive_cases_outside_cohort":len(new_positive),
 "full_source_positive_outside_cohort":sum(x["source_type"]=="FULL_FROZEN_SNAPSHOT" for x in new_positive),
 "historical_rule_matches_outside_cohort":sum(x["new_historical_rule"]>0 for x in new_positive),
 "strict_added_line_historical_full_candidates":len(strict),
 "priority_counts":dict(counter),
 "strict_candidate_ids":[x["case_id"] for x in strict],
 "new_positive_ids":[x["case_id"] for x in new_positive],
 "errors":[{"case_id":x["case_id"],"error":x["error"]} for x in rows if x["status"]!="SCAN_COMPLETE"],
 "suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
 "codeql_expected":"2.25.6",
 "source_archive_digest":source["transfer"]["sha256"],
 "limitations":["Scanner alert not automatically vulnerability.","O3 alone does not provide a W/P causal comparison.",
 "Recheck historical warning source-to-sink mechanism and repository provenance before expanding cohort.",
 "Functional completeness not established; filtered sources provisional."],
 "rows":rows}
(OUT/"SCREEN65_ITER3_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
md=["# Third-iteration O-only CodeQL screen: 65 cases","",
 "CodeQL 2.25.6, JavaScript security-extended. Archived frozen prepatch SARIF as baseline.",
 "**Do not treat alert counts as confirmed vulnerabilities or O/W/P treatment effects.**",
 "",
 "Cases scanned: "+str(summary["completed_scans"])+"/65.",
 "Newly scanner-positive cases outside existing 14: "+str(len(new_positive))+"/51.",
 "Full-snapshot positives outside existing 14: "+str(summary["full_source_positive_outside_cohort"])+".",
 "Strongest new target-class on-added-line candidates: "+str(summary["strict_candidate_ids"])+".",
 "",
 "| Case | Cohort | Source | Apply/scan | New strong | New conservative | Historical-class | Added-line historical | Tier |",
 "|---|---|---|---|---:|---:|---:|---:|---|"]
for r in rows:
 md.append("| %05d | %s | %s | %s | %s | %s | %s | %s | %s |"%(
 r["case_id"],"already 14" if r["cohort"]=="EXISTING_14" else "new",
 r["source_type"],r["status"],
 str(r["new_strong"]) if r["new_strong"] is not None else "N/A",
 str(r["new_conservative"]) if r["new_conservative"] is not None else "N/A",
 str(r["new_historical_rule"]),str(r["historical_rule_on_added_line"]),r["candidate_priority"]))
md.extend(["","## New cohort candidates and scanner traces",""])
for r in new_positive:
 md.append("### %05d — %s"%(r["case_id"],r["candidate_priority"]))
 data=json.loads((OUT/("CASE_%05d"%r["case_id"])/"RESULT.json").read_text())
 for a in data.get("findings",{}).get("new_strong_findings",[]):
  md.append("- "+a["rule"]+" at "+a["path"]+":"+str(a["line"])+
    (" [added line]" if a["on_added_line"] else " [not added line]")+
    (" [historical class]" if a["historical_rule_class"] else "")+
    " — "+a["message"][:150])
 md.append("")
md.extend(["## Eligibility rules","- Prioritize full snapshots and historical class recurrence, with source-to-sink review.",
 "- New warnings in unrelated rule classes are exploratory only.",
 "- Never automatically add provisional filtered sources based only on scanner findings.",
 "- A patch that fails to apply or has no new findings does not count as a positive."])
(OUT/"SCREEN65_ITER3_SCREENING_REPORT.md").write_text("\n".join(md)+"\n")
with zipfile.ZipFile(OUT/"SCREEN65_ITER3_REPORT.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name in ["SCREEN65_ITER3_SUMMARY.json","SCREEN65_ITER3_RESULTS.csv","SCREEN65_ITER3_SCREENING_REPORT.md"]:
  z.write(OUT/name,name)
 for r in rows:
  f=OUT/("CASE_%05d"%r["case_id"])/"RESULT.json"
  if f.exists():z.write(f,"per_case/CASE_%05d.json"%r["case_id"])
print("SCREEN65_ITER3_FINAL",json.dumps({k:summary[k] for k in ["stage","completed_scans","failed_scans","positive_cases_outside_cohort","strict_candidate_ids","priority_counts"]}),flush=True)
