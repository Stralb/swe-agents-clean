from pathlib import Path
from zipfile import ZipFile
import json
r=Path.home()/"research_artifacts"
src=r/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
targets={"08152":"RPL7_RUN_23E9AAB8295A.zip","12344":"RPL7_RUN_E0EDE434153B.zip"}
obj={}
for case,name in targets.items():
 with ZipFile(src/name) as z:
  names=[{"path":i.filename,"size":i.file_size} for i in z.infolist() if not i.is_dir()]
  docs=[]
  for x in z.infolist():
   if x.is_dir() or x.filename.startswith("REPO/") or x.file_size>25000:continue
   try:docs.append({"path":x.filename,"text":z.read(x).decode("utf-8")[:12000]})
   except UnicodeDecodeError:pass
  obj[case]={"filenames":names,"documents":docs}
out=r/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/INSPECT.json"
out.write_text(json.dumps(obj,indent=2))
print(json.dumps({k:{"docs":[x["path"] for x in v["documents"]],"repo_files":sum(x["path"].startswith("REPO/") for x in v["filenames"])} for k,v in obj.items()},indent=2))
