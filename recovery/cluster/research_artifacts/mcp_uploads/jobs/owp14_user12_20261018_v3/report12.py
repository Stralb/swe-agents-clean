#!/usr/bin/env python3
"""Read finished per-case scanner reports; produce a reproducible O-only CSV and Markdown summary."""
import csv,json,os
from pathlib import Path
ROOT=Path.home()/"research_artifacts"/"prevention_pilot_phase2"
SCAN=ROOT/"owp14_user12_o_codeql_job71159"
PRE=ROOT/"owp14_user12_o_preflight_job71153"
OUT=ROOT/("owp14_user12_o_report_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
sc=json.loads((SCAN/"SUMMARY.json").read_text())
pr=json.loads((PRE/"SUMMARY.json").read_text())
assert sc["stage"]=="COMPLETE" and len(sc["cases"])==12 and pr["case_count_applied"]==12
fields=["case_id","patch_applied","source_type","stage","codeql_version","before_findings","after_findings","new_strong","new_conservative","historical_target_new_strong","historical_target_new_conservative","new_strong_on_added_lines","target_rule","functional_validation","patch_sha256"]
rows=[];details=[]
for cid in sorted(int(k) for k in pr["cases"].keys()):
 d=json.loads((SCAN/("CASE_%05d"%cid)/"RESULT.json").read_text())
 assert d["case_id"]==cid
 row={"case_id":cid,"patch_applied":pr["cases"][str(cid)]["patch_applied"],
 "source_type":d["source_type"],"stage":d["stage"],
 "codeql_version":d["current_codeql_version"],
 "before_findings":d.get("codeql_before_total"),"after_findings":d.get("codeql_after_total"),
 "new_strong":d.get("new_strong_total"),"new_conservative":d.get("new_conservative_total"),
 "historical_target_new_strong":d.get("new_strong_target_rule"),
 "historical_target_new_conservative":d.get("new_conservative_target_rule"),
 "new_strong_on_added_lines":d.get("new_strong_on_added_line"),
 "target_rule":d["target_rule"],"functional_validation":d["functional_status"],
 "patch_sha256":d["patch_sha256"]}
 rows.append(row);details.append(d)
with (OUT/"O_ONLY_CODEQL12.csv").open("x",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
tick=chr(96)
md=["# O-only CodeQL evaluation: 12 uploaded patches","",
 "These are exploratory scan results, not an O/W/P treatment comparison.",
 "Missing O cases: 8461, 15151. Uploaded W and P patches: none.",
 "All twelve O patches applied to the frozen repository copies.",
 "CodeQL suite: "+sc["suite"]+". CodeQL version: "+sc["codeql_version"]+".",
 "Historical exact issue-body versions: unverified. Filtered base cases are provisional.",
 "Functional correctness: NOT VALIDATED; scanner-negative does not imply correctness.",
 "",
 "| Case | Source | Scanner | Before | After | New alerts | New historical-target alerts | On added lines |",
 "|---|---|---|---:|---:|---:|---:|---:|"]
for r in rows:
 def show(k):return str(r[k]) if r[k] is not None else "N/A"
 md.append("| %05d | %s | %s | %s | %s | %s | %s | %s |"%(
  r["case_id"],"filtered" if r["source_type"]!="FULL_FROZEN_SNAPSHOT" else "full",
  r["stage"],show("before_findings"),show("after_findings"),show("new_strong"),
  show("historical_target_new_strong"),show("new_strong_on_added_lines")))
md.extend(["","## New scanner alerts, by case",""])
for d in details:
 md.append("### Case %05d: %s"%(d["case_id"],d["stage"]))
 if d["stage"]!="SCAN_COMPLETE":
  md.append("No usable scanner outcome: "+d.get("error","unknown failure"))
 else:
  if not d["new_strong_alerts"]:md.append("No strong-new CodeQL alerts.")
  for v in d["new_strong_alerts"]:
   md.append("- "+v["rule"]+" at "+v["path"]+":"+str(v["line"])+
     (" [on added line]" if v["on_added_line"] else " [not on added line]")+
     (" [historical target class]" if v["historical_target_rule"] else "")+
     " — "+v["message"].replace("\n"," ")[:180])
 md.append("")
md.extend(["## Caveats",
 "- New scanner findings require source-to-sink manual adjudication; a rule ID alone is not a confirmed exploit.",
 "- Four cases have provisional filtered source snapshots.",
 "- Models, prompts and generation contexts for historical O attempts must remain separately labelled.",
 "- No claim of vulnerability prevention is possible without paired W and P patches and functionality verification."])
(OUT/"O_ONLY_CODEQL12.md").write_text("\n".join(md)+"\n")
(OUT/"O_ONLY_CODEQL12.json").write_text(json.dumps({"rows":rows,"scanner_success":sum(r["stage"]=="SCAN_COMPLETE" for r in rows),
 "new_alerts":sum(r["new_strong"] or 0 for r in rows),
 "new_historical_target_alerts":sum(r["historical_target_new_strong"] or 0 for r in rows),
 "functional_validated":0},indent=2)+"\n")
print("REPORT_COMPLETE",OUT,flush=True)
