#!/usr/bin/env python3
"""Read-only check of baseline SARIF and strong-delta heuristic for 14 unique cases."""
import csv,json,os,re
from pathlib import Path
P=Path.home()/"research_artifacts/prevention_pilot_phase2"
ids=[668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759]
out=P/("dual_o_attribution14_job"+os.environ["SLURM_JOB_ID"]);out.mkdir(exist_ok=False)
def load(p):return json.loads(p.read_text())
def findings(p):
 obj=load(p);res=[]
 for run in obj.get("runs",[]):
  for v in run.get("results",[]):
   loc=(v.get("locations") or [{}])[0].get("physicalLocation",{})
   res.append({"rule":v.get("ruleId"),"path":loc.get("artifactLocation",{}).get("uri"),
    "line":loc.get("region",{}).get("startLine"),"message":v.get("message",{}).get("text",""),
    "fp":v.get("partialFingerprints") or {}})
 return res
items=[];bad=[]
for cid in ids:
 name="CASE_%05d"%cid
 for j,base in enumerate((P/"screen65_codeql_job70675",P/"screen65_second_codeql_job70782")):
  if j==1 and cid in (16633,25473):base=P/"screen65_second_codeql_retry_job70880"
  c=base/name
  scan=load(c/"RESULT.json")
  if scan.get("stage")!="SCAN_COMPLETE":raise RuntimeError("Failed scan: "+str(cid))
  if not scan["findings"]["new_strong_count"]:continue
  before=(P/"screen65_second_codeql_job70782"/name/"before.sarif") if j==1 and cid in (16633,25473) else c/"before.sarif"
  pre=findings(before)
  for f in scan["findings"]["new_strong_findings"]:
   same=[v for v in pre if v["rule"]==f["rule"] and v["path"]==f["path"]]
   exact_msg=[v for v in same if v["message"]==f["message"]]
   line_eq=[v for v in same if v["line"]==f["line"]]
   scores=[{"line":v["line"],"message":v["message"][:180]} for v in sorted(same,key=lambda v:abs((v["line"] or 0)-(f["line"] or 0)))[:4]]
   flag=("SAME_RULE_PATH_LINE_EXISTED" if line_eq else
         "SAME_RULE_PATH_MESSAGE_EXISTED" if exact_msg else
         "SAME_RULE_PATH_EXISTED" if same else "NO_BASELINE_MATCHING_RULE_PATH")
   row={"case":cid,"attempt":"O"+str(j+1),"rule":f["rule"],"path":f["path"],"line":f["line"],
     "baseline_same_rule_file_count":len(same),"baseline_same_message_count":len(exact_msg),
     "baseline_same_line_count":len(line_eq),"flag":flag,"nearest_baseline_findings":scores}
   items.append(row)
   if flag!="NO_BASELINE_MATCHING_RULE_PATH":bad.append(row)
with (out/"ALERTS_14.json").open("x") as f:json.dump({"new_strong_finding_count":len(items),
 "baseline_rule_path_existing_count":len(bad),"cases_with_baseline_same_rule_path":sorted({x["case"] for x in bad}),
 "alerts":items},f,indent=2);f.write("\n")
with (out/"ALERTS_14.csv").open("x",newline="") as f:
 cols=["case","attempt","rule","path","line","baseline_same_rule_file_count",
  "baseline_same_message_count","baseline_same_line_count","flag"]
 w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(items)
print("ATTRIBUTION_DONE",len(items),"flags",len(bad),"flagged_cases",sorted({x["case"] for x in bad}),flush=True)
