#!/usr/bin/env python3
"""Versioned O/P exploratory CodeQL comparison; historical W arm pending; no causal claim."""
from pathlib import Path
import csv,json,os
ROOT=Path.home()/"research_artifacts"/"prevention_pilot_phase2"
OSCAN=ROOT/"owp14_user12_o_codeql_job71159"
PSCAN=ROOT/"owp14_user14_p_codeql_job71204"
OUT=ROOT/("owp14_user14_op_comparison_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
o=json.loads((OSCAN/"SUMMARY.json").read_text())
p=json.loads((PSCAN/"SUMMARY.json").read_text())
assert o["stage"]==p["stage"]=="COMPLETE"
assert o["case_count"]==12 and p["case_count"]==14
assert o["codeql_version"]==p["codeql_version"]=="2.25.6"
assert o["suite"]==p["suite"]
target={}
with (ROOT/"owp14_target_specific_index_job71021/TARGET_SPECIFIC_INDEX_CORRECTED.csv").open(newline="") as f:
 for row in csv.DictReader(f):target[int(row["case_id"])]=row
fields=["case_id","repository","source_type","preexisting_O_target_recurred","O_present","O_stage","P_stage",
"O_new_strong","P_new_strong","delta_P_minus_O_strong",
"O_new_conservative","P_new_conservative","delta_P_minus_O_conservative",
"O_historical_rule","P_historical_rule","O_on_added_line","P_on_added_line",
"baseline_match","O_functionality","P_functionality",
"O_patch_sha256","P_patch_sha256"]
rows=[];details={}
for cid in sorted(target):
 strid=str(cid)
 old=o["cases"].get(strid)
 new=p["cases"].get(strid)
 assert new,("missing P",cid)
 if old:
  assert old["source_type"]==new["source_type"],("source mode mismatch",cid)
  assert old["target_rule"]==new["target_rule"],("rule mismatch",cid)
  oba=old.get("baseline_sarif_sha256");pba=new.get("baseline_sarif_sha256")
  match=oba==pba and bool(oba)
 else:
  match=None
 def count(x,k):
  return x.get(k) if x and x["stage"]=="SCAN_COMPLETE" else None
 def difference(a,b):return b-a if a is not None and b is not None else None
 oc=count(old,"new_strong_total");pc=count(new,"new_strong_total")
 ow=count(old,"new_conservative_total");pw=count(new,"new_conservative_total")
 row={"case_id":cid,"repository":target[cid]["repository"],
  "source_type":new["source_type"],
  "preexisting_O_target_recurred":target[cid]["any_O_target_warning"],
  "O_present":old is not None,
  "O_stage":old["stage"] if old else "MISSING",
  "P_stage":new["stage"],
  "O_new_strong":oc,"P_new_strong":pc,"delta_P_minus_O_strong":difference(oc,pc),
  "O_new_conservative":ow,"P_new_conservative":pw,"delta_P_minus_O_conservative":difference(ow,pw),
  "O_historical_rule":count(old,"new_strong_target_rule"),
  "P_historical_rule":count(new,"new_strong_target_rule"),
  "O_on_added_line":count(old,"new_strong_on_added_line"),
  "P_on_added_line":count(new,"new_strong_on_added_line"),
  "baseline_match":match,
  "O_functionality":old.get("functional_status") if old else "MISSING",
  "P_functionality":new.get("functional_status"),
  "O_patch_sha256":old.get("patch_sha256") if old else None,
  "P_patch_sha256":new.get("patch_sha256")}
 rows.append(row)
 details[strid]={"O":{k:old.get(k) for k in ["stage","new_strong_alerts","new_conservative_alerts"]} if old else None,
                 "P":{k:new.get(k) for k in ["stage","new_strong_alerts","new_conservative_alerts"]}}
assert len(rows)==14
with (OUT/"OP_CODEQL_COMPARISON.csv").open("x",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
comparable=[x for x in rows if x["O_stage"]==x["P_stage"]=="SCAN_COMPLETE" and x["baseline_match"]]
problems=[x for x in rows if x["O_present"] and x["baseline_match"] is False]
md=["# O versus P scanner comparison — exploratory","",
 "14 P patches and 12 O patches, separately generated; 2 O cases not uploaded.",
 "Warning-informed W patches have not been supplied. No complete O/W/P experiment is possible.",
 "No independent feature/acceptance checks have established functional correctness.",
 "P requirements were designed retrospectively from historical warnings and are not a prospective deployment policy.",
 "CodeQL CLI "+p["codeql_version"]+"; query suite "+p["suite"]+".",
 "Historical issue bodies as of the original pull requests have not been verified.",
 "Four cases were built from filtered source snapshots and remain provisional.",
 "",
 "- O scans completed: "+str(sum(x["stage"]=="SCAN_COMPLETE" for x in o["cases"].values()))+"/12",
 "- P scans completed: "+str(sum(x["stage"]=="SCAN_COMPLETE" for x in p["cases"].values()))+"/14",
 "- Directly comparable scanner runs: "+str(len(comparable))+"/12",
 "- Baseline mismatches: "+str(len(problems)),
 "- Cases with fewer new scanner alerts under P (where comparable): "+str(sum(x["delta_P_minus_O_strong"]<0 for x in comparable)),
 "- Cases with more new scanner alerts under P (where comparable): "+str(sum(x["delta_P_minus_O_strong"]>0 for x in comparable)),
 "- Cases with equal new scanner alerts: "+str(sum(x["delta_P_minus_O_strong"]==0 for x in comparable)),
 "",
 "| Case | Source | O new | P new | O target | P target | Baseline match |",
 "|---|---|---:|---:|---:|---:|---|"]
for x in rows:
 def f(k):return str(x[k]) if x[k] is not None else "N/A"
 md.append("| %05d | %s | %s | %s | %s | %s | %s |"%(
 x["case_id"],"filtered" if x["source_type"]!="FULL_FROZEN_SNAPSHOT" else "full",
 f("O_new_strong"),f("P_new_strong"),f("O_historical_rule"),f("P_historical_rule"),f("baseline_match")))
md.extend(["","## Causal interpretation limits",
 "- These are unadjusted scanner counts, not causal prevention rates.",
 "- A reduction can reflect incomplete implementation, changed coding strategy, or genuine prevention.",
 "- Equality of rule IDs does not establish the same source-to-sink mechanism.",
 "- Assess task completion and independently validate the targeted security property before claiming success.",
 "- Restrict confirmatory estimates to historically eligible full-frozen cases after provenance checks.",
 "- Do not pool different coding models, interfaces or generation runs without accounting for cohort."])
(OUT/"OP_CODEQL_COMPARISON.md").write_text("\n".join(md)+"\n")
(OUT/"OP_FINDINGS_DETAILS.json").write_text(json.dumps(details,indent=2)+"\n")
(OUT/"OP_CODEQL_SUMMARY.json").write_text(json.dumps({"rows":rows,"comparable_count":len(comparable),
 "unmatched_baselines":[x["case_id"] for x in problems],
 "old_scanned":sum(x["stage"]=="SCAN_COMPLETE" for x in o["cases"].values()),
 "p_scanned":sum(x["stage"]=="SCAN_COMPLETE" for x in p["cases"].values()),
 "warning_arm_available":False,"functionality_validated":0},indent=2)+"\n")
print("OP_REPORT_COMPLETE",OUT,"paired_scans",len(comparable),flush=True)
