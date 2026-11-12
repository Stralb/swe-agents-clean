#!/usr/bin/env python3
"""Package exact SIGG 03581 R02/R08 CodeQL artifacts without re-running or modifying scans."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_sigg_r02_r08_v6_20261030_r1"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
P1=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
files={}
for run in ["R02","R08"]:
 s=D/("results_"+run)
 result=json.loads((s/"RESULT.json").read_text())
 assert result["run_id"]==run and result["status"]=="CODEQL_SCAN_COMPLETE"
 assert result["source_files"]==397 and result["functional_status"]=="NOT_VERIFIED"
 assert result["checks"]["patch_check"]["exit"]==0
 assert result["checks"]["patch_apply"]["exit"]==0
 assert result["checks"]["db_create"]["exit"]==0
 assert result["checks"]["scan"]["exit"]==0
 assert sha(s/"after.sarif")==result["after_sarif_sha256"]
 assert sha(s/("PATCH_"+run+".patch"))==result["patch_sha256"]
 assert sha(s/("RECEIPT_"+run+".json"))==result["receipt_sha256"]
 for n in ["RESULT.json","warning_delta.json","after.sarif","apply_check.log","apply.log","create.log","scan.log", "PATCH_"+run+".patch","RECEIPT_"+run+".json"]:
  files["trial_"+run+"/"+n]=s/n
for n in ["RESULT.json","baseline.sarif"]:
 files["baseline/"+n]=BASE/n
for n in ["RESULT.json","after.sarif"]:
 files["historical_P1/"+n]=P1/n
assert sha(BASE/"baseline.sarif")==json.loads((BASE/"RESULT.json").read_text())["sarif_sha256"]
assert sha(P1/"after.sarif")==json.loads((P1/"RESULT.json").read_text())["after_sarif_sha256"]
out=D/"ARNO_SIGG_R02_R08_FULL_CODEQL_V6_EVIDENCE.zip"
assert not out.exists()
with ZipFile(out,"x",compression=ZIP_DEFLATED,compresslevel=8) as z:
 for n,p in sorted(files.items()):z.write(p,n)
 z.writestr("README.txt","Frozen case 03581, two first-attempt independent minimal-context generation trials R02 and R08.\nRun-scoped raw SARIF, CodeQL+apply logs and input patches/receipts preserved, with historical P1 and baseline SARIF.\nCanonical full source ZIP deliberately excluded (10.3 MB), SHA-256 recorded in trial RESULT.json. Check that full functional acceptance has not been verified.\nCodeQL warnings are not proven security vulnerabilities, and absence of a warning is not proof of security.\n")
with ZipFile(out) as z:assert z.testzip() is None
meta={"status":"VERIFIED_AND_PACKAGED","case":"03581","runs":["R02","R08"],
 "file_count":len(files)+1,"zip_relative_path":str(out.relative_to(R)),
 "zip_sha256":sha(out),"zip_bytes":out.stat().st_size}
(D/"PACKAGE_MANIFEST.json").write_text(json.dumps(meta,indent=2)+"\n")
print(json.dumps(meta,indent=2),flush=True)
