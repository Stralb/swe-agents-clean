#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
R=Path.home()/"research_artifacts";D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
OUT=D/"ARNO_AC6_V6_CODEQL_EVIDENCE.zip"
assert not OUT.exists(),"Do not overwrite an existing evidence package"
roots=[D/"summary_v6c",D/"results_v6c"]
files=[D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip",D/"scan_ac_v6c.py",D/"scan_ac_v6c.sbatch"]
for root in roots:
 assert root.is_dir(),str(root)
 files.extend(sorted(p for p in root.rglob("*") if p.is_file()))
manifest=[]
with ZipFile(OUT,"x",compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for p in files:
  rel=str(p.relative_to(D))
  b=p.read_bytes()
  z.writestr(rel,b)
  manifest.append({"name":rel,"size":len(b),"sha256":hashlib.sha256(b).hexdigest()})
 z.writestr("PACKAGE_MANIFEST.json",json.dumps({"files":manifest,"file_count":len(manifest)},indent=2))
with ZipFile(OUT) as z:assert z.testzip() is None
(D/"EVIDENCE_PACKAGE_INFO.json").write_text(json.dumps({"path":str(OUT),"size_bytes":OUT.stat().st_size,
 "sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),"file_count":len(manifest)},indent=2))
print((D/"EVIDENCE_PACKAGE_INFO.json").read_text(),flush=True)
