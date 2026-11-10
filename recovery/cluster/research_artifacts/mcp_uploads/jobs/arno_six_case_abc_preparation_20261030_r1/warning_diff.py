#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json,hashlib
R=Path.home()/"research_artifacts"
P=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
O=R/"mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1"
cases=("03429","03581","08152","12344","31207","32759")
def signals(p):
 c=Counter();det={}
 for run in json.loads(p.read_text()).get("runs",[]):
  for v in run.get("results",[]):
   loc=v.get("locations",[]);ph=loc[0].get("physicalLocation",{}) if loc else {}
   uri=ph.get("artifactLocation",{}).get("uri","").replace("\\","/")
   msg=" ".join((v.get("message",{}).get("text") or "").split())
   key=(v.get("ruleId",""),uri,msg)
   c[key]+=1
   if key not in det:det[key]={"rule":key[0],"file":key[1],"message":key[2],"line":ph.get("region",{}).get("startLine"),"snippet":ph.get("region",{}).get("snippet",{}).get("text")}
 return c,det
summary=[]
for case in cases:
 info=json.loads((O/("CASE_"+case+"_RESEARCHER.json")).read_text())
 root=P/("CASE_"+case)/info["p1_id"]
 before,_=signals(B/("CASE_"+case)/"baseline.sarif")
 after,det=signals(root/"after.sarif")
 delta=after-before
 rows=[{**det[k],"count":v} for k,v in delta.items()]
 data={"case":case,"source_kind":info["source_kind"],"baseline":sum(before.values()),"after":sum(after.values()),"new":sum(delta.values()),"warnings":rows}
 (O/("CASE_"+case+"_WARNING_DELTA_RESEARCHER.json")).write_text(json.dumps(data,indent=2))
 summary.append(data)
(O/"WARNINGS_RESEARCHER.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
