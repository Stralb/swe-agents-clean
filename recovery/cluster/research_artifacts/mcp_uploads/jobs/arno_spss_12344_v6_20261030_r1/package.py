from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime,timezone
import json,hashlib
ROOT=Path.home()/"research_artifacts"
D=ROOT/"mcp_uploads/jobs/arno_spss_12344_v6_20261030_r1"
OUT=D/"results"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
SCGG=ROOT/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
r=json.loads((OUT/"RESULT.json").read_text())
assert r["status"]=="CODEQL_SCAN_COMPLETE" and r["case"]=="12344"
assert r["first_delivery_patch_modified"] is False
assert r["codeql_version"]=="2.25.6" and r["source_files"]==10341
assert r["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
assert r["baseline_total"]==758 and r["historical_p1_total"]==763 and r["previous_scgg_total"]==763
for kind,name in [
 ("patch","PATCH_SPSCGG_12344_R1.patch"),
 ("receipt","RECEIPT_SPSCGG_12344_R1.json"),
 ("implementation_prompt","IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md"),
 ("after_sarif","after.sarif")]:
 hashkey={"patch":"patch_sha256","receipt":"receipt_sha256",
          "implementation_prompt":"implementation_prompt_sha256","after_sarif":"after_sarif_sha256"}[kind]
 assert sha_file(OUT/name)==r[hashkey]
assert sha_file(BASE/"baseline.sarif")==json.loads((BASE/"RESULT.json").read_text())["sarif_sha256"]
assert sha_file(P1/"after.sarif")==json.loads((P1/"RESULT.json").read_text())["after_sarif_sha256"]
assert sha_file(SCGG/"after.sarif")==json.loads((SCGG/"RESULT.json").read_text())["after_sarif_sha256"]
files={}
for filename in ["RESULT.json","warning_delta.json","after.sarif","PATCH_SPSCGG_12344_R1.patch",
  "RECEIPT_SPSCGG_12344_R1.json","IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md",
  "codeql_version.log","apply_check.log","apply.log","create.log","analyze.log"]:
 files["self_prompting/"+filename]=OUT/filename
for fn in ["RESULT.json","baseline.sarif"]:files["frozen_baseline/"+fn]=BASE/fn
for fn in ["RESULT.json","after.sarif"]:files["historical_P1/"+fn]=P1/fn
for fn in ["RESULT.json","warning_delta.json","after.sarif","PATCH_SCGG_12344_R1.patch","RECEIPT_SCGG_12344_R1.json"]:
 files["previous_SCGG/"+fn]=SCGG/fn
for fn in ["evaluate.py","scan.sbatch"]:files["evaluator/"+fn]=D/fn
readme=f"""Single-case self-prompting SCGG evaluation, case 12344, Wits V6, frozen 10341-file FILTERED_SOURCE_PROVISIONAL snapshot.
Pre-existing CodeQL baseline: {r['baseline_total']} findings.
Historical first patch: {r['historical_p1_total']}, {r['historical_p1_new']} new.
Previous SCGG: {r['previous_scgg_total']}, {r['previous_scgg_new']} new.
Self-prompted SCGG: {r['after_total']}, {r['new_vs_baseline']} new.
Evaluation method: line-agnostic multiset comparison (ruleId, relative file, normalized message).
CodeQL security-extended, version 2.25.6. Both original agent patch and self-generated prompt SHA-verified.
Do not claim native Windows functional correctness; no real DPAPI test in this archive.
The SHA of the source zip is in self_prompting/RESULT.json, source archive itself is not included.
"""
path=D/"ARNO_SPSCGG_12344_FULL_V6_CODEQL_EVIDENCE.zip"
assert not path.exists()
with ZipFile(path,"x",ZIP_DEFLATED,compresslevel=7) as z:
 for name,src in sorted(files.items()):z.write(src,name)
 z.writestr("README.txt",readme)
with ZipFile(path) as z:assert z.testzip() is None
info={"status":"VERIFIED_AND_PACKAGED","case":"12344",
 "zip_relative_path":str(path.relative_to(ROOT)),
 "bytes":path.stat().st_size,"sha256":sha_file(path),
 "entries":len(files)+1,"after_total":r["after_total"],
 "new_findings":r["new_vs_baseline"],"by_rule":r["new_by_rule"],
 "created_utc":datetime.now(timezone.utc).isoformat()}
(D/"PACKAGE_INFO.json").write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2),flush=True)
