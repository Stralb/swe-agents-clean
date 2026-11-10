#!/usr/bin/env python3
"""Read completed O/W/P CodeQL runs and report descriptive scanner comparisons, never causal prevention claims."""
from pathlib import Path
from datetime import datetime,timezone
import csv,json,os
ROOT=Path.home()/"research_artifacts"/"prevention_pilot_phase2"
SCANS={"O":ROOT/"owp14_user12_o_codeql_job71159",
       "W":ROOT/"owp14_user14_w_codeql_job71209",
       "P":ROOT/"owp14_user14_p_codeql_job71204"}
OUT=ROOT/("owp14_allarm_comparison_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
summary={a:json.loads((p/"SUMMARY.json").read_text()) for a,p in SCANS.items()}
assert all(v["stage"]=="COMPLETE" for v in summary.values())
assert [summary[a]["case_count"] for a in ("O","W","P")]==[12,14,14]
assert {v["codeql_version"] for v in summary.values()}=={"2.25.6"}
assert len({v["suite"] for v in summary.values()})==1
target={}
with (ROOT/"owp14_target_specific_index_job71021/TARGET_SPECIFIC_INDEX_CORRECTED.csv").open(newline="") as f:
 for row in csv.DictReader(f):target[int(row["case_id"])]=row
assert len(target)==14
fields=["case_id","repo","snapshot","historical_target_rule","prior_O_target_reproduced","baselines_match"]
for arm in ("O","W","P"):
 fields += [arm+"_scan",arm+"_new",arm+"_new_conservative",arm+"_target",arm+"_target_added_line",arm+"_functional",arm+"_patch_sha256"]
fields+=["W_minus_O_new","P_minus_O_new","W_minus_O_target","P_minus_O_target"]
rows=[];details={}
for cid in sorted(target):
 meta=target[cid];item={}
 for arm in ("O","W","P"):
  path=SCANS[arm]/("CASE_%05d"%cid)/"RESULT.json"
  item[arm]=json.loads(path.read_text()) if path.exists() else None
  if item[arm]:assert item[arm]["case_id"]==cid and item[arm]["arm"]==arm
 assert item["W"] and item["P"]
 def ok(arm):return item[arm] is not None and item[arm]["stage"]=="SCAN_COMPLETE"
 active=[a for a in ("O","W","P") if ok(a)]
 shas=[item[a].get("baseline_sarif_sha256") for a in active]
 equal=bool(shas) and all(shas) and len(set(shas))==1
 snapshot=item["W"]["source_type"]
 assert item["P"]["source_type"]==snapshot
 if item["O"]: assert item["O"]["source_type"]==snapshot
 for a in ("W","P"):
  assert item[a]["target_rule"]==meta["target_rule"]
 row={"case_id":cid,"repo":meta["repository"],"snapshot":snapshot,
      "historical_target_rule":meta["target_rule"],
      "prior_O_target_reproduced":meta["any_O_target_warning"],
      "baselines_match":equal}
 for a in ("O","W","P"):
  d=item[a]
  row[a+"_scan"]=d["stage"] if d else "NOT_UPLOADED"
  row[a+"_new"]=d.get("new_strong_total") if ok(a) else None
  row[a+"_new_conservative"]=d.get("new_conservative_total") if ok(a) else None
  row[a+"_target"]=d.get("new_strong_target_rule") if ok(a) else None
  row[a+"_target_added_line"]=sum(v["historical_target_rule"] and v["on_added_line"] for v in d["new_strong_alerts"]) if ok(a) else None
  row[a+"_functional"]=d.get("functional_status") if d else "NOT_UPLOADED"
  row[a+"_patch_sha256"]=d.get("patch_sha256") if d else None
 for a in ("W","P"):
  row[a+"_minus_O_new"]=row[a+"_new"]-row["O_new"] if ok(a) and ok("O") and equal else None
  row[a+"_minus_O_target"]=row[a+"_target"]-row["O_target"] if ok(a) and ok("O") and equal else None
 rows.append(row)
 details[str(cid)]={}
 for a in ("O","W","P"):
  if not item[a]:details[str(cid)][a]=None
  else:details[str(cid)][a]={"stage":item[a]["stage"],"new_strong_alerts":item[a].get("new_strong_alerts"),
     "new_conservative_alerts":item[a].get("new_conservative_alerts"),"error":item[a].get("error")}
assert len(rows)==14
with (OUT/"OWP14_SCANNER_COMPARISON.csv").open("x",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
paired=[r for r in rows if r["O_scan"]==r["W_scan"]==r["P_scan"]=="SCAN_COMPLETE" and r["baselines_match"]]
counts={"three_arm_paired_cases":len(paired),
 "O_scans":sum(r["O_scan"]=="SCAN_COMPLETE" for r in rows),
 "W_scans":sum(r["W_scan"]=="SCAN_COMPLETE" for r in rows),
 "P_scans":sum(r["P_scan"]=="SCAN_COMPLETE" for r in rows),
 "missing_O":[r["case_id"] for r in rows if r["O_scan"]=="NOT_UPLOADED"],
 "filtered_provisional":[r["case_id"] for r in rows if r["snapshot"]!="FULL_FROZEN_SNAPSHOT"],
 "historical_target_previously_reproduced_count":sum(r["prior_O_target_reproduced"]=="True" for r in rows),
 "total_alerts_paired":{a:sum(r[a+"_new"] for r in paired) for a in ("O","W","P")},
 "target_alerts_paired":{a:sum(r[a+"_target"] for r in paired) for a in ("O","W","P")},
 "W_fewer_total_cases":sum(r["W_minus_O_new"]<0 for r in paired),
 "W_same_total_cases":sum(r["W_minus_O_new"]==0 for r in paired),
 "W_more_total_cases":sum(r["W_minus_O_new"]>0 for r in paired),
 "P_fewer_total_cases":sum(r["P_minus_O_new"]<0 for r in paired),
 "P_same_total_cases":sum(r["P_minus_O_new"]==0 for r in paired),
 "P_more_total_cases":sum(r["P_minus_O_new"]>0 for r in paired),
 "W_no_target_given_O_target":[r["case_id"] for r in paired if r["O_target"]>0 and r["W_target"]==0],
 "P_no_target_given_O_target":[r["case_id"] for r in paired if r["O_target"]>0 and r["P_target"]==0]}
metadata={
 "timestamp_utc":datetime.now(timezone.utc).isoformat(),
 "outcome":"exploratory scanner comparison only",
 "CodeQL_version":"2.25.6",
 "suite":summary["O"]["suite"],
 "jobs":{"O":71159,"W":71209,"P":71204},
 "issue_asof_PR_provenance_verified":False,
 "functional_acceptance_verified":False,
 "agent_generation_cohort_comparability_verified":False,
 "historical_rule_match_is_not_mechanism_proof":True,
 "cases":rows,
 "counts":counts}
(OUT/"OWP14_SUMMARY.json").write_text(json.dumps(metadata,indent=2)+"\n")
(OUT/"OWP14_NEW_ALERTS_ALL_ARMS.json").write_text(json.dumps(details,indent=2)+"\n")
lines=["# O/W/P static-analysis comparison — 14 cases","",
 "IMPORTANT: This is a descriptive CodeQL comparison, not proof of vulnerability prevention.",
 "The historical W warning is a retrospective oracle intervention, not a deployable new-task workflow.",
 "Original issue version at historical pre-PR time is not verified.",
 "Functional correctness has not been independently validated; an incomplete patch may have fewer warnings.",
 "Models, random seeds and generation sessions were not proven homogeneous.",
 "Four filtered source snapshots remain provisional; two O patches were not uploaded.",
 "CodeQL 2.25.6; javascript-security-extended suite; source CodeQL SARIF baseline hashes checked.",
 "",
 "## Summary statistics",""]
for k,v in counts.items():lines.append("- "+k.replace("_"," ")+": "+str(v))
lines.extend(["","## Results by case",
 "| Case | Source | O new | W new | P new | O target | W target | P target | Same baseline |",
 "|---|---|---:|---:|---:|---:|---:|---:|---|"])
for r in rows:
 def value(k):return str(r[k]) if r[k] is not None else "N/A"
 lines.append("| %05d | %s | %s | %s | %s | %s | %s | %s | %s |"%(
  r["case_id"],"filtered" if r["snapshot"]!="FULL_FROZEN_SNAPSHOT" else "full",
  value("O_new"),value("W_new"),value("P_new"),
  value("O_target"),value("W_target"),value("P_target"),value("baselines_match")))
lines.extend(["","## Full new scanner findings per arm",""])
for r in rows:
 cid=r["case_id"];lines.append("### Case %05d"%cid)
 for arm in ("O","W","P"):
  entry=details[str(cid)][arm]
  if not entry:lines.append("- "+arm+": not uploaded");continue
  if entry["stage"]!="SCAN_COMPLETE":lines.append("- "+arm+": "+entry["stage"]+" "+str(entry["error"]));continue
  xs=entry["new_strong_alerts"] or []
  if not xs:lines.append("- "+arm+": no new scanner findings")
  for x in xs:
   lines.append("- "+arm+": "+x["rule"]+" at "+x["path"]+":"+str(x["line"])+
                (" (added line)" if x["on_added_line"] else " (not added line)")+
                (" (selected warning class)" if x["historical_target_rule"] else "")+
                " — "+x["message"].replace("\n"," ")[:180])
 lines.append("")
lines.extend(["## Interpretation caveats",
 "- Differences in warnings are not automatically caused by the intervention; functional tests and mechanism adjudication are necessary.",
 "- A CodeQL rule-name match does not imply identical source and sink or proven exploitation.",
 "- Original-issue-only O patches come from a separate historical generation cohort unless generation settings are confirmed.",
 "- Scanner-negative implementations may be functionally incomplete.",
 "- Missing O outcomes and filtered snapshots are explicitly represented, not imputed."])
(OUT/"OWP14_SCANNER_COMPARISON.md").write_text("\n".join(lines)+"\n")
print("OWP_REPORT_COMPLETE",OUT,"PAIRED",len(paired),"STATS",json.dumps(counts),flush=True)
