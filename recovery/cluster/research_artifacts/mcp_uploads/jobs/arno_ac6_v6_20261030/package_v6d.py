#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
OUT=D/"ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL.zip"
assert not OUT.exists(),"Refuse to overwrite evidence package"
paths=[D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip",D/"scan_ac_v6c.py",D/"scan_ac_v6c.sbatch",
       D/"aggregate_v6d.py",D/"aggregate_final_v6.sbatch"]
for root in (D/"summary_v6d",D/"results_v6c"):
 assert root.is_dir(),"Results directory missing "+str(root)
 paths.extend(sorted(p for p in root.rglob("*") if p.is_file()))
manifest=[]
with ZipFile(OUT,"x",compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for p in paths:
  raw=p.read_bytes()
  name=str(p.relative_to(D))
  z.writestr(name,raw)
  manifest.append({"name":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
 z.writestr("PACKAGE_MANIFEST.json",json.dumps({"file_count":len(manifest),"files":manifest},indent=2))
with ZipFile(OUT) as z:assert z.testzip() is None
record={"status":"EVIDENCE_PACKAGED","path":str(OUT),"bytes":OUT.stat().st_size,
        "sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),"file_count":len(manifest)}
(D/"EVIDENCE_PACKAGE_INFO_FINAL.json").write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
