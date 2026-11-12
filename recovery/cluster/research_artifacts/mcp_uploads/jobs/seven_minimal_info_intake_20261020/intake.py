#!/usr/bin/env python3
from pathlib import Path
import zipfile,json,hashlib
root=Path.home()/"research_artifacts"
directory=root/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
out=root/"mcp_uploads/seven_minimal_info_intake_20261020"
out.mkdir(parents=True,exist_ok=True)
ids=["03429","03581","08152","12344","22223","31207","32759"]
summary=[]
for i in ids:
 src=directory/("CASE_"+i+"_O.zip")
 with zipfile.ZipFile(src) as z:
  n=z.namelist()
  issue=z.read("ISSUE.md").decode("utf-8","replace")
  instruction=z.read("RUN_INSTRUCTIONS.md").decode("utf-8","replace")
  (out/("ISSUE_"+i+".txt")).write_text(issue)
  repo_files=[x for x in n if x.startswith("REPO/") and not x.endswith("/")]
  summary.append(dict(case_id=i,source_bytes=src.stat().st_size,repo_files=len(repo_files),issue_bytes=len(issue.encode()),issue_sha=hashlib.sha256(issue.encode()).hexdigest(),source_sha=hashlib.sha256(src.read_bytes()).hexdigest(),heading=issue.splitlines()[0],run_instructions=instruction,issue_text=issue))
(out/"ISSUE_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in x.items() if k not in ("issue_text","run_instructions")} for x in summary],indent=2))
