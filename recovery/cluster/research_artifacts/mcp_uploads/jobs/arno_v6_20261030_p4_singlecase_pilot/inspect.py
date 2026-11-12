#!/usr/bin/env python3
from pathlib import Path
import json,zipfile
root=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
out=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_v6_20261030_p4_singlecase_pilot"
m=json.loads((root/"MANIFEST.json").read_text())
for x in m["runs"]:
 if x["case_id"]!="22223":continue
 with zipfile.ZipFile(root/"run_zips"/(x["run_id"]+".zip")) as z:
  names=z.namelist()
  print("CONDITION",x["condition"],"RUN",x["run_id"],"MEMBERS",len(names),"ROOTS",sorted(set(n.split("/")[0] for n in names)),"\n")
  p=z.read("PROMPT.md").decode("utf-8")
  issue=z.read("ISSUE.md").decode("utf-8")
  (out/("inspection_"+x["condition"]+"_prompt.txt")).write_text(p)
  (out/("inspection_"+x["condition"]+"_issue.txt")).write_text(issue)
  print("PROMPT_BYTES",len(p),"ISSUE_BYTES",len(issue))
print("INSPECTION_COMPLETE")
