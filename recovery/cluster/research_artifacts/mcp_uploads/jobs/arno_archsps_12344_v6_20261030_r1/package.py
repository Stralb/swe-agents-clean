from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
import hashlib, json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_archsps_12344_v6_20261030_r1"
O=D/"results"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
H=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
C=R/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
S=R/"mcp_uploads/jobs/arno_spss_12344_v6_20261030_r1/results"
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
result=json.loads((O/"RESULT.json").read_text())
assert result["case"]=="12344" and result["run_id"]=="ARCHSPSCGG_12344_R1"
assert result["status"]=="CODEQL_SCAN_COMPLETE"
assert result["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
assert result["source_files"]==10341
assert result["codeql_version"]=="2.25.6"
assert result["baseline_total"]==758
assert result["historical_p1_total"]==763
assert result["previous_scgg_total"]==763
assert result["previous_self_prompt_total"]==763
assert result["original_first_delivery_patch_modified"] is False
for step in ["version","apply_check","apply","create","analyze"]:
 assert result["checks"][step]["exit"]==0,(step,result["checks"][step])
assert digest(O/"after.sarif")==result["after_sarif_sha256"]
for kind,name in [("patch","PATCH_ARCHSPSCGG_12344_R1.patch"),
                  ("receipt","RECEIPT_ARCHSPSCGG_12344_R1.json"),
                  ("prompt","IMPLEMENTATION_PROMPT_ARCHSPSCGG_12344_R1.md")]:
 assert digest(O/name)==result[kind+"_sha256"]
for loc,filename,key in [(B,"baseline.sarif","sarif_sha256"),
                         (H,"after.sarif","after_sarif_sha256"),
                         (C,"after.sarif","after_sarif_sha256"),
                         (S,"after.sarif","after_sarif_sha256")]:
 assert digest(loc/filename)==json.loads((loc/"RESULT.json").read_text())[key]
delta=json.loads((O/"warning_delta.json").read_text())
assert sum(x["count"] for x in delta["new"])==result["new_vs_baseline"]
files={}
for fn in ["RESULT.json","warning_delta.json","after.sarif","PATCH_ARCHSPSCGG_12344_R1.patch",
           "RECEIPT_ARCHSPSCGG_12344_R1.json","IMPLEMENTATION_PROMPT_ARCHSPSCGG_12344_R1.md",
           "version.log","apply_check.log","apply.log","create.log","analyze.log"]:
 files[f"ARCHSPSCGG/{fn}"]=O/fn
for prefix,src,filenames in [
 ("BASELINE",B,["RESULT.json","baseline.sarif"]),
 ("HISTORICAL_P1",H,["RESULT.json","after.sarif"]),
 ("PRIOR_SCGG",C,["RESULT.json","warning_delta.json","after.sarif"]),
 ("PRIOR_SELF_PROMPT",S,["RESULT.json","warning_delta.json","after.sarif"])
]:
 for fn in filenames:files[f"{prefix}/{fn}"]=src/fn
for filename in ["eval.py","scan.sbatch"]:
 files[f"EVALUATOR/{filename}"]=D/filename
summary={
 "case":"12344","condition":"Architecture-constrained self-prompting",
 "source_kind":result["source_kind"],"source_file_count":result["source_files"],
 "suite":result["suite"],"codeql_version":result["codeql_version"],
 "new_warning_matching":"line-agnostic multiset of ruleId, relative path and normalized message",
 "before_baseline":result["baseline_total"],
 "historical_p1_new":result["historical_p1_new"],
 "prior_scgg_new":result["previous_scgg_new"],
 "prior_self_prompt_new":result["previous_self_prompt_new"],
 "architecture_constrained_new":result["new_vs_baseline"],
 "after_total":result["after_total"],
 "new_by_rule":result["new_by_rule"],
 "functional_status":"NOT_VERIFIED",
 "native_windows_status":"NOT_RUN",
 "study_note":"Development-case intervention explicitly shaped by prior observations. Do not treat as blind or causally conclusive."
}
readme=("Case 12344 architecture-constrained self-prompt experiment; Wits V6 job 79024.\n"
        "Warning counts: baseline 758; historical P1 +5; SCGG +5; self-prompt +5; "
        f"architecture-constrained +{result['new_vs_baseline']}.\n"
        "Source kind: FILTERED_SOURCE_PROVISIONAL (10341 files); NOT a complete independently validated repository.\n"
        "Windows native credential functionality has NOT been verified; scanner silence does not imply security.\n"
        "Full reproducibility data includes exact original patch/prompt/receipt, scanner logs, raw SARIF, comparison script, "
        "SHA256 digests in RESULT.json and an archive manifest.\n")
dest=D/"ARNO_ARCHSPSCGG_12344_FULL_CODEQL_V6_EVIDENCE.zip"
assert not dest.exists()
manifest={"created_utc":datetime.now(timezone.utc).isoformat(),
          "source_zip_sha256":result["source_zip_sha256"],
          "source_tree_sha256":result["source_tree_sha256"],
          "files":{}}
for name,p in sorted(files.items()):
 manifest["files"][name]={"bytes":p.stat().st_size,"sha256":digest(p)}
with ZipFile(dest,"x",compression=ZIP_DEFLATED,compresslevel=7) as z:
 for name,src in sorted(files.items()):z.write(src,name)
 z.writestr("SUMMARY.json",json.dumps(summary,indent=2)+"\n")
 z.writestr("MANIFEST.json",json.dumps(manifest,indent=2)+"\n")
 z.writestr("README.txt",readme)
with ZipFile(dest) as z:assert z.testzip() is None
info={"status":"VERIFIED_AND_PACKAGED","archive_relative_path":str(dest.relative_to(R)),
      "size_bytes":dest.stat().st_size,"sha256":digest(dest),"entries":len(files)+3,
      "new_vs_baseline":result["new_vs_baseline"],"baseline_total":result["baseline_total"],
      "after_total":result["after_total"],"rules":result["new_by_rule"]}
(D/"PACKAGE_INFO.json").write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2),flush=True)
