#!/usr/bin/env python3
"""Read-only filesystem inventory for final NEW70 source archives and original O-arm patches."""
from pathlib import Path
from datetime import datetime,timezone
import os,json
R=Path.home()/"research_artifacts"
terms=[
 "Step1_NEW70_FINAL.zip",
 "NEW70_Phase6_Step2_Mapping_FINAL_v1.0.zip",
 "NEW70_Phase6_Producing_Changes_FINAL_v1.0.csv",
 "CASE_08461_O.patch",
 "CASE_15151_O.patch",
 "D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv"
]
skip={".git","node_modules","__pycache__",".venv","venv","env","site-packages",".cache","repos","repo","codeql_db","codeql-dbs"}
matches={n:[] for n in terms}
dirs=0;files=0
for current,subs,names in os.walk(R):
 rel=Path(current).relative_to(R)
 if len(rel.parts)>9: subs[:]=[];continue
 subs[:]=[s for s in subs if s not in skip]
 dirs+=1;files+=len(names)
 for n in names:
  if n in matches:
   p=Path(current)/n
   try:matches[n].append({"relative_path":str(p.relative_to(R)),"bytes":p.stat().st_size})
   except OSError:pass
out={"utc":datetime.now(timezone.utc).isoformat(),"dirs":dirs,"files":files,"source_targets":matches}
p=R/"mcp_uploads/jobs/arno_oct28_provenance_source_find/RESULT.json"
p.parent.mkdir(parents=True,exist_ok=True)
if p.exists():raise RuntimeError("Refusing to overwrite")
p.write_text(json.dumps(out,indent=2))
print(json.dumps({"status":"SOURCE_FIND_COMPLETE","report":str(p),"found":{name:len(xs) for name,xs in matches.items()}},indent=2))
