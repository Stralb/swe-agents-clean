#!/usr/bin/env python3
import json,os,zipfile,collections
from pathlib import Path
r=Path.home()/"research_artifacts"
out=r/"mcp_uploads/jobs/arno_patch_integration_inspection_v1"
out.mkdir(exist_ok=True,parents=True)
paths=[
"mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation",
"mcp_uploads/jobs/arno_ac6_v6_20261030",
"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots",
"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2",
]
report={}
for name in paths:
 root=r/name
 entries=[]
 if not root.exists():continue
 for base,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d!="__pycache__"]
  for f in files:
   p=Path(base)/f
   if p.suffix.lower() in (".patch",".diff",".sarif",".json",".zip",".txt",".csv",".log",".md"):
    rec={"path":str(p.relative_to(r)),"size":p.stat().st_size}
    if p.suffix.lower()==".zip":
     try:
      with zipfile.ZipFile(p) as z:
       names=z.namelist()
       rec["zip_files"]=len(names)
       rec["zip_patch_members"]=[v for v in names if v.lower().endswith((".patch",".diff"))][:75]
       rec["zip_relevant"]=[v for v in names if any(s in v.lower() for s in ("patch","prompt","receipt","after.sarif","baseline.sarif","result.json","metadata"))][:40]
     except Exception as e: rec["zip_error"]=str(e)
    entries.append(rec)
 report[name]={"total_relevant_files":len(entries),"entries":entries[:250]}
(out/"SOURCE_ARTIFACT_DISCOVERY.json").write_text(json.dumps(report,indent=2)+"\n")
for name,v in report.items():
 print(name,"files",v["total_relevant_files"],"zips",sum(x["path"].endswith(".zip") for x in v["entries"]))
 for e in v["entries"]:
  if e["path"].endswith(".zip") and e["size"]<100000000:
   print(" ZIP",e["path"],"patches",e.get("zip_patch_members",[])[:6],"samples",e.get("zip_relevant",[])[:10])
