from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime,timezone
import json,hashlib
ROOT=Path.home()/"research_artifacts"
DIR=ROOT/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
PREVIOUS={"08152":{"run":"RPL7_RUN_23E9AAB8295A","job":"78972","source_kind":"FULL_FROZEN_SNAPSHOT","baseline":4,"historical_new":1},
"12344":{"run":"RPL7_RUN_E0EDE434153B","job":"78973","source_kind":"FILTERED_SOURCE_PROVISIONAL","baseline":758,"historical_new":5}}
def hashfile(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
files={}
out={}
for case,meta in PREVIOUS.items():
 rdir=DIR/("results_"+case)
 bdir=BASE/("CASE_"+case)
 pdir=P1/("CASE_"+case)/meta["run"]
 result=json.loads((rdir/"RESULT.json").read_text())
 b=json.loads((bdir/"RESULT.json").read_text())
 h=json.loads((pdir/"RESULT.json").read_text())
 assert result["status"]=="CODEQL_SCAN_COMPLETE",(case,result["status"])
 assert result["codeql_version"]=="2.25.6"
 assert result["source_kind"]==meta["source_kind"]
 assert result["baseline_total"]==meta["baseline"]
 assert result["historical_p1_new"]==meta["historical_new"]
 assert result["checks"]["apply_check"]["exit"]==0
 assert result["checks"]["apply"]["exit"]==0
 assert result["checks"]["database_create"]["exit"]==0
 assert result["checks"]["analysis"]["exit"]==0
 assert hashfile(rdir/"after.sarif")==result["after_sarif_sha256"]
 assert hashfile(rdir/(f"PATCH_SCGG_{case}_R1.patch"))==result["patch_sha256"]
 assert hashfile(rdir/(f"RECEIPT_SCGG_{case}_R1.json"))==result["receipt_sha256"]
 assert hashfile(bdir/"baseline.sarif")==b["sarif_sha256"]
 assert hashfile(pdir/"after.sarif")==h["after_sarif_sha256"]
 assert b["source_kind"]==meta["source_kind"]
 assert result["original_patch_modified"] is False
 for fn in ["RESULT.json","warning_delta.json","after.sarif",f"PATCH_SCGG_{case}_R1.patch",
   f"RECEIPT_SCGG_{case}_R1.json","version.log","apply_check.log","apply.log","database_create.log","analysis.log"]:
  files[f"scgg/{case}/{fn}"]=rdir/fn
 for fn in ["RESULT.json","baseline.sarif"]:files[f"baseline/{case}/{fn}"]=bdir/fn
 for fn in ["RESULT.json","after.sarif"]:files[f"historical_P1/{case}/{fn}"]=pdir/fn
 out[case]={"job":meta["job"],"status":result["status"],"source_kind":result["source_kind"],
   "baseline_total":result["baseline_total"],"historical_p1_total":result["historical_p1_total"],
   "historical_p1_new":result["historical_p1_new"],"scgg_total":result["after_total"],
   "scgg_new":result["new_vs_baseline"],"new_by_rule":result["new_by_rule"],
   "historical_p1_remaining":result["historical_p1_remaining"],
   "historical_p1_absent":result["historical_p1_absent"],
   "patch_sha256":result["patch_sha256"],"receipt_sha256":result["receipt_sha256"],
   "source_zip_sha256":result["input_source_zip_sha256"],
   "source_tree_sha256":result["source_tree_sha256"],"sarif_sha256":result["after_sarif_sha256"],
   "source_files":result["source_files"],"functional_status":"NOT_VERIFIED"}
for fn in ["evaluate.py","scan_08152.sbatch","scan_12344.sbatch"]:
 files["research_scripts/"+fn]=DIR/fn
summary={
 "experiment":"SCGG replication 08152+12344 first-delivered patches",
 "codeql_version":"2.25.6",
 "suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
 "warning_identity":"line-agnostic (ruleId, relative file, normalized message) multiset",
 "cases":out,
 "caveats":["These cases have been investigated previously, not pristine held-out cases",
   "12344 source was FILTERED_SOURCE_PROVISIONAL",
   "Zero scanner alerts is not evidence of no vulnerabilities",
   "Functional and native Windows integration not fully verified",
   "No changes to generated first-delivered patches prior to scanner evaluation"],
 "created_utc":datetime.now(timezone.utc).isoformat()
}
summaryfile=DIR/"ARNO_SCGG_TWO_REPLICATIONS_CODEQL_SUMMARY.json"
assert not summaryfile.exists()
summaryfile.write_text(json.dumps(summary,indent=2)+"\n")
files["SUMMARY.json"]=summaryfile
notes=f"""SCGG REPLICATION RESULTS 08152 + 12344 (2026-10-30)
Same frozen CodeQL 2.25.6 security-extended suite and before/after multiset comparison as prior runs.
08152: baseline 4, historical P1 new 1, SCGG new {out["08152"]["scgg_new"]} (after {out["08152"]["scgg_total"]}).
12344: filtered source provisional, baseline 758, historical P1 new 5, SCGG new {out["12344"]["scgg_new"]} (after {out["12344"]["scgg_total"]}).
Neither scanner silence nor mocked tests establishes full security or functional correctness.
Pre-existing source ZIPs are on V6 and referenced by SHA256; not included in this evidence ZIP.
"""
dst=DIR/"ARNO_SCGG_TWO_REPLICATIONS_FULL_CODEQL_V6_EVIDENCE.zip"
assert not dst.exists()
with ZipFile(dst,"x",ZIP_DEFLATED,compresslevel=7) as z:
 for name,path in sorted(files.items()):z.write(path,name)
 z.writestr("README.txt",notes)
with ZipFile(dst) as z:assert z.testzip() is None
pkg={"status":"VERIFIED_AND_PACKAGED","zip_relative_path":str(dst.relative_to(ROOT)),
     "bytes":dst.stat().st_size,"sha256":hashfile(dst),"files":len(files)+1,"cases":out}
info=DIR/"ARNO_SCGG_TWO_REPLICATIONS_EVIDENCE_INFO.json"
assert not info.exists()
info.write_text(json.dumps(pkg,indent=2)+"\n")
print(json.dumps(pkg,indent=2),flush=True)
