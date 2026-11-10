#!/usr/bin/env python3
"""Package immutable case-03581 minctx static scan evidence; no database modifications."""
from pathlib import Path
import zipfile,hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_minctx_03581_v6_scan_20261030_r1"
O=D/"results_v2"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
P1=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
rec=json.loads((O/"RESULT.json").read_text())
assert rec["status"]=="CODEQL_SCAN_COMPLETE"
files={}
for n in ["RESULT.json","warning_delta.json","PATCH_MINCTX_03581_R1.patch","RECEIPT_MINCTX_03581_R1.json","after.sarif","apply.log","apply_check.log","codeql_create.log","codeql_analyze.log"]:
 files["minimal_context/"+n]=O/n
for n in ["RESULT.json","baseline.sarif"]:
 files["baseline/"+n]=BASE/n
for n in ["RESULT.json","after.sarif"]:
 files["historical_P1/"+n]=P1/n
for p in files.values():assert p.is_file()
out=D/"MINCTX_03581_CODEQL_EVIDENCE_V6.zip"
assert not out.exists()
with zipfile.ZipFile(out,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in files.items():z.write(p,name)
 z.writestr("README.txt","Case 03581, independent minimal-context agent patch applied against 397-file frozen full repository.\nCodeQL javascript-security-extended baseline-relative analysis.\nThe historical P1 warning signatures are absent; one new js/file-system-race arises in workflow-commentary-service.ts.\nNo complete task-acceptance or security exploit verification was run. Scanner findings are not confirmed vulnerabilities.\nOriginal source ZIP remains on the Wits cluster and is identified by SHA-256 in RESULT.json.\n")
with zipfile.ZipFile(out) as z:assert z.testzip() is None
metadata={"status":"PACKAGED","case":"03581","run_id":"MINCTX_03581_R1","zip_relative_path":str(out.relative_to(R)),
 "bytes":out.stat().st_size,"sha256":sha(out),"file_count":len(files)+1,
 "baseline_total":rec["baseline_total"],"original_p1_new":rec["original_p1_new"],"minimal_new":rec["new_vs_baseline"],
 "functional_status":rec["functional_status"]}
(D/"EVIDENCE_PACKAGE_INFO.json").write_text(json.dumps(metadata,indent=2))
print(json.dumps(metadata,indent=2),flush=True)
