from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime,timezone
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_archgen_22223_32759_v6_20261030_r1"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
H=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
RUNS={"22223":"RPL7_RUN_3D0780CD09D2","32759":"RPL7_RUN_C24121FB6FE5"}
EXPECTED={"22223":{"before":41,"historical":44,"new":0},
          "32759":{"before":12,"historical":14,"new":1}}
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
files={}
summary={"experiment":"ARCHGEN two-case exploratory generalised architectural prompting",
         "source_kind":"FULL_FROZEN_SNAPSHOT","codeql":"2.25.6",
         "suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
         "comparison":"line-agnostic (ruleId, path, normalized message) multiset",
         "limitations":["One coding conversation permits cross-case contamination",
                        "22223 agent receipt absent; 32759 receipt supplied twice identically",
                        "No native Windows validation of 32759",
                        "No logged-in ChatGPT download validation of 22223",
                        "Exploratory, previously studied development-cohort cases",
                        "Static analysis results do not establish vulnerability absence"],
         "cases":{}}
for case,run in RUNS.items():
 out=D/("results_"+case)
 baseline=B/("CASE_"+case)
 hist=H/("CASE_"+case)/run
 r=json.loads((out/"RESULT.json").read_text())
 b=json.loads((baseline/"RESULT.json").read_text())
 h=json.loads((hist/"RESULT.json").read_text())
 assert r["case"]==case and r["status"]=="CODEQL_SCAN_COMPLETE"
 assert r["source_kind"]=="FULL_FROZEN_SNAPSHOT" and r["codeql_version"]=="2.25.6"
 assert r["baseline_total"]==EXPECTED[case]["before"]
 assert r["historical_p1_total"]==EXPECTED[case]["historical"]
 assert r["new_vs_baseline"]==EXPECTED[case]["new"]
 assert r["first_delivered_patch_modified"] is False
 for step in ["version","apply_check","apply","db_create","analysis"]:
  assert r["checks"][step]["exit"]==0,(case,step)
 assert sha(out/"after.sarif")==r["after_sarif_sha256"]
 assert sha(baseline/"baseline.sarif")==b["sarif_sha256"]
 assert sha(hist/"after.sarif")==h["after_sarif_sha256"]
 patch=f"PATCH_ARCHGEN_{case}_R1.patch"
 prompt=f"IMPLEMENTATION_PROMPT_ARCHGEN_{case}_R1.md"
 assert sha(out/patch)==r["patch_sha256"]
 assert sha(out/prompt)==r["prompt_sha256"]
 if case=="32759":
  receipt=f"RECEIPT_ARCHGEN_{case}_R1.json"
  assert sha(out/receipt)==r["receipt_sha256"]
 delta=json.loads((out/"warning_delta.json").read_text())
 assert sum(x["count"] for x in delta["new"])==r["new_vs_baseline"]
 assert sum(x["count"] for x in delta["historical_p1_new"])==r["historical_p1_new"]
 for fn in ["RESULT.json","warning_delta.json","after.sarif",patch,prompt,
            "version.log","apply_check.log","apply.log","db_create.log","analysis.log"]:
  files[f"ARCHGEN_{case}/{fn}"]=out/fn
 if case=="32759":files[f"ARCHGEN_{case}/{receipt}"]=out/receipt
 for fn in ["RESULT.json","baseline.sarif"]:files[f"BASELINE_{case}/{fn}"]=baseline/fn
 for fn in ["RESULT.json","after.sarif"]:files[f"HISTORICAL_P1_{case}/{fn}"]=hist/fn
 summary["cases"][case]={
    "status":r["status"],"baseline_total":r["baseline_total"],
    "historical_p1_total":r["historical_p1_total"],
    "historical_p1_new":r["historical_p1_new"],
    "archgen_after_total":r["after_total"],"archgen_new":r["new_vs_baseline"],
    "archgen_new_by_rule":r["new_by_rule"],"historical_absent":r["historical_p1_absent"],
    "historical_remaining":r["historical_p1_remaining"],
    "source_files":r["source_files"],"source_zip_sha256":r["source_zip_sha256"],
    "source_tree_sha256":r["source_tree_sha256"],"patch_sha256":r["patch_sha256"],
    "prompt_sha256":r["prompt_sha256"],"receipt_status":r["receipt_status"],
    "scanner_sarif_sha256":r["after_sarif_sha256"],"functional_status":r["functional_status"]
 }
for fn in ["evaluate.py","scan_22223.sbatch","scan_32759.sbatch"]:
 files[f"EVALUATOR/{fn}"]=D/fn
summary["created_utc"]=datetime.now(timezone.utc).isoformat()
sfile=D/"ARCHGEN_TWO_CASES_V6_VERIFIED_RESULTS.json"
assert not sfile.exists()
sfile.write_text(json.dumps(summary,indent=2)+"\n")
files["SUMMARY.json"]=sfile
manifest={"created_utc":summary["created_utc"],"files":{}}
for name,p in sorted(files.items()):
 manifest["files"][name]={"bytes":p.stat().st_size,"sha256":sha(p)}
archive=D/"ARNO_ARCHGEN_22223_32759_FULL_V6_CODEQL_EVIDENCE.zip"
assert not archive.exists()
with ZipFile(archive,"x",ZIP_DEFLATED,compresslevel=7) as z:
 for name,p in sorted(files.items()):z.write(p,name)
 z.writestr("MANIFEST.json",json.dumps(manifest,indent=2)+"\n")
 z.writestr("README.txt","Independent V6 CodeQL 2.25.6 security-extended scans for cases 22223 and 32759. 22223 new=0, 32759 new=1. Source ZIPs are not embedded; content hashes are in results. Missing receipt for 22223; non-native test limitations apply.\n")
with ZipFile(archive) as z:assert z.testzip() is None
info={"status":"VERIFIED_AND_PACKAGED","archive_relative_path":str(archive.relative_to(R)),
      "archive_bytes":archive.stat().st_size,"sha256":sha(archive),
      "entries":len(files)+2,"cases":summary["cases"]}
(D/"EVIDENCE_PACKAGE_INFO.json").write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2),flush=True)
