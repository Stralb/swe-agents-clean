#!/usr/bin/env python3
"""Non-destructive metadata correction and evidence packaging for 32759 minimal context."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_minctx_32759_v6_scan_20261030_r1"
OUT=D/"results"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_32759"
P1=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_32759/RPL7_RUN_C24121FB6FE5"
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
raw=json.loads((OUT/"RESULT.json").read_text())
assert raw["case"]=="03581" and raw["run_id"]=="MINCTX_32759_R1"
assert raw["source_file_count"]==23 and raw["source_kind"]=="FULL_FROZEN_SNAPSHOT"
assert raw["source_zip_sha256"]=="cf9fdbcc6d38d0cb42e47599c061c72b8f571c7c914d7010a404d88af8b5af07"
assert raw["status"]=="CODEQL_SCAN_COMPLETE"
assert raw["new_vs_baseline"]==0 and raw["historical_p1_signatures_remaining"]==0
assert raw["apply_check"]["exit"]==raw["apply"]["exit"]==raw["codeql_database_create"]["exit"]==raw["codeql_analyze"]["exit"]==0
assert sha(OUT/"PATCH_MINCTX_32759_R1.patch")==raw["patch_sha256"]
assert sha(OUT/"RECEIPT_MINCTX_32759_R1.json")==raw["receipt_sha256"]
assert sha(OUT/"after.sarif")==raw["after_sarif_sha256"]
assert sha(BASE/"baseline.sarif")==json.loads((BASE/"RESULT.json").read_text())["sarif_sha256"]
assert sha(P1/"after.sarif")==json.loads((P1/"RESULT.json").read_text())["after_sarif_sha256"]
corrected={**raw,"case":"32759",
 "metadata_correction":{"field":"case","raw_value":"03581","corrected_value":"32759",
 "reason":"Scan wrapper retained a constant from the 03581 template; validated against unique run ID, frozen source SHA-256, 23-file repo, and patch SHA-256. Scanner outputs unchanged.",
 "original_result_json_sha256":sha(OUT/"RESULT.json")}}
cor=OUT/"RESULT_CASEID_CORRECTED.json"
assert not cor.exists()
cor.write_text(json.dumps(corrected,indent=2)+"\n")
f={
 "scan/RESULT_ORIGINAL.json":OUT/"RESULT.json",
 "scan/RESULT_CASEID_CORRECTED.json":cor,
 "scan/warning_delta.json":OUT/"warning_delta.json",
 "scan/PATCH_MINCTX_32759_R1.patch":OUT/"PATCH_MINCTX_32759_R1.patch",
 "scan/RECEIPT_MINCTX_32759_R1.json":OUT/"RECEIPT_MINCTX_32759_R1.json",
 "scan/after.sarif":OUT/"after.sarif",
 "scan/apply_check.log":OUT/"apply_check.log",
 "scan/apply.log":OUT/"apply.log",
 "scan/codeql_create.log":OUT/"codeql_create.log",
 "scan/codeql_analyze.log":OUT/"codeql_analyze.log",
 "baseline/RESULT.json":BASE/"RESULT.json",
 "baseline/baseline.sarif":BASE/"baseline.sarif",
 "historical_P1/RESULT.json":P1/"RESULT.json",
 "historical_P1/after.sarif":P1/"after.sarif"
}
dest=D/"MINCTX_32759_CODEQL_EVIDENCE_V6.zip"
assert not dest.exists()
with ZipFile(dest,"x",compression=8,compresslevel=7) as z:
 for name,p in f.items(): z.write(p,name)
 z.writestr("README.txt","32759 minimal-context R1: scanner comparison against unchanged frozen 23-file source.\nThe initial RESULT.json had mislabeled metadata case=03581, corrected in RESULT_CASEID_CORRECTED.json. No scan output was changed.\nZero NEW CodeQL findings versus frozen baseline; Windows runtime behavior not tested. Scanner silence is not proof of exploit resistance.\n")
with ZipFile(dest) as z:assert z.testzip() is None
status={"case":"32759","status":"EVIDENCE_PACKAGED","zip_relative_path":str(dest.relative_to(R)),
 "zip_sha256":sha(dest),"zip_bytes":dest.stat().st_size,"files":len(f)+1,
 "corrected_result_sha256":sha(cor)}
info=D/"EVIDENCE_PACKAGE_INFO.json";assert not info.exists()
info.write_text(json.dumps(status,indent=2)+"\n")
print(json.dumps(status,indent=2))
