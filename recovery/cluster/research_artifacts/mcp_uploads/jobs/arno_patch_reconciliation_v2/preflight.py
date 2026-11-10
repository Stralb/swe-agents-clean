#!/usr/bin/env python3
import hashlib,zipfile,json
from pathlib import Path
r=Path.home()/"research_artifacts"
out=r/"mcp_uploads/jobs/arno_patch_reconciliation_v2";out.mkdir(parents=True,exist_ok=True)
m=r/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
e=r/"mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation"
s=r/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
b=r/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
up=r/"mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
a=r/"mcp_uploads/jobs/arno_ac6_v6_20261030/ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL_V6E.zip"
def sha(x):return hashlib.sha256(x).hexdigest()
def sf(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
manifest=json.loads((m/"MANIFEST.json").read_text())["runs"]
evaluations={x["run_id"]:x for x in json.loads((e/"EVALUATION.json").read_text())["runs"]}
assert len(manifest)==len(evaluations)==21
assert sf(up)=="c88bc9da10a830ffccd6c318a4da446440ed7aeb16ad4ef07f37c725edd3e9e6"
with zipfile.ZipFile(up) as z:
 assert z.testzip() is None and len(z.namelist())==42
 for x in manifest:
  rid=x["run_id"];cid=x["case_id"];ev=evaluations[rid];base=b/("CASE_"+cid)/"baseline.sarif"
  p=s/("CASE_"+cid)/rid/("PATCH_"+rid+".patch")
  sarif=s/("CASE_"+cid)/rid/"after.sarif"
  result=json.loads((s/("CASE_"+cid)/rid/"RESULT.json").read_text())
  assert ev["case_id"]==cid and ev["condition"]==x["condition"]
  assert z.read("PATCH_"+rid+".patch")==p.read_bytes()
  assert sf(p)==ev["patch_sha256"]==result["patch_sha256"]
  assert sf(sarif)==ev["scan_sarif_sha256"]==result["after_sarif_sha256"]
  assert sf(base)==result["baseline_sarif_sha256"]
  assert sf(m/"run_zips"/(rid+".zip"))==x["sha256"]
with zipfile.ZipFile(a) as z:
 assert z.testzip() is None
 for c in ["03429","03581","08152","12344","31207","32759"]:
  for arm in ["MECHANISM","PROSPECTIVE_BUILD"]:
   pre="results_v6c/CASE_"+c+"/"+arm+"/"
   patch=z.read(pre+"PATCH.patch");result=json.loads(z.read(pre+"RESULT.json"));sarif=z.read(pre+"after.sarif")
   assert sha(patch)==result["patch_sha256"],(c,arm,"patch hash mismatch")
   assert sha(sarif)==result["after_sarif_sha256"],(c,arm,"scan hash mismatch")
   assert len(z.read(pre+"RECEIPT.json"))>0
report={"status":"VERIFIED","rpl_matched_patch_scan_prompt_runs":21,"ac_matched_patch_scan_receipt_runs":12,
"rpl_returned_patch_archive_sha":sf(up),"ac_evidence_archive_sha":sf(a),"source_files_modified":False}
(out/"PREFLIGHT_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
