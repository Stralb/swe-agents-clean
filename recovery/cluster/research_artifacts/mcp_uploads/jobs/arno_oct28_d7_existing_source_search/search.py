#!/usr/bin/env python3
"""Search existing cluster artifacts for the exact original 342-root D7 CSV without any upload."""
import os,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
SHA="be316e7eb5708d4cf5ac71baafaf82f84fbe15fbb44deb651ac76712d24083b4"
skip={".git","node_modules","__pycache__",".venv","venv","env","site-packages",".cache","repos","repo","codeql_db","codeql-dbs"}
found=[];candidates=[];dirs_seen=0;files_seen=0
for dp,dirnames,files in os.walk(R):
 depth=len(Path(dp).relative_to(R).parts)
 if depth>8:
  dirnames[:]=[];continue
 dirnames[:]=[d for d in dirnames if d not in skip]
 dirs_seen+=1;files_seen+=len(files)
 for n in files:
  lname=n.lower()
  if not (n.endswith(".csv") and (("d7" in lname) or ("root" in lname and "342" in lname))):
   continue
  p=Path(dp)/n
  try:
   sz=p.stat().st_size
   if sz>5000000:continue
   h=hashlib.sha256(p.read_bytes()).hexdigest()
   obj={"path":str(p),"bytes":sz,"sha256":h}
   candidates.append(obj)
   if h==SHA:found.append(obj)
  except OSError:continue
O=R/"mcp_uploads/jobs/arno_oct28_d7_existing_source_search/RESULT.json"
O.parent.mkdir(parents=True,exist_ok=True)
if O.exists():raise RuntimeError("Report already exists")
report={"utc":datetime.now(timezone.utc).isoformat(),"dirs_seen":dirs_seen,"files_seen":files_seen,"found_exact":found,"other_candidates":candidates[:250]}
O.write_text(json.dumps(report,indent=2))
print(json.dumps({"status":"DONE","dirs_seen":dirs_seen,"files_seen":files_seen,"found_exact":found,"other_candidates_count":len(candidates),"report":str(O)},indent=2))
