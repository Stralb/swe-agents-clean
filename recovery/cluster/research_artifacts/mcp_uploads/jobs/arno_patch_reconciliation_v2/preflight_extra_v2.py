#!/usr/bin/env python3
"""Last read-only checks before 42GB V2 import."""
import sqlite3,json,hashlib,zipfile
from pathlib import Path
R=Path.home()/"research_artifacts"
M=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
E=R/"mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
AC=R/"mcp_uploads/jobs/arno_ac6_v6_20261030/ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL_V6E.zip"
DB=R/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
cx=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
def sha(data):return hashlib.sha256(data).hexdigest()
manifest=json.loads((M/"MANIFEST.json").read_text())["runs"]
rpl={r["run_id"]:r for r in json.loads((E/"EVALUATION.json").read_text())["runs"]}
for item in manifest:
 run=item["run_id"];cid=item["case_id"]
 with zipfile.ZipFile(M/"run_zips"/(run+".zip")) as z:prompt=z.read("PROMPT.md")
 assert sha(prompt)==item["prompt_sha256"],("prompt",run)
 if item["condition"]=="P1":
  old=cx.execute("SELECT patch_blob,content_sha256 FROM arno_generated_patches WHERE run_id=?",(run,)).fetchone()
  assert old and sha(old[0])==old[1]==rpl[run]["patch_sha256"],("original P1 hash",run)
with zipfile.ZipFile(AC) as z:
 for case in ["03429","03581","08152","12344","31207","32759"]:
  baseline=(B/("CASE_"+case)/"baseline.sarif").read_bytes()
  for arm in ["MECHANISM","PROSPECTIVE_BUILD"]:
   result=json.loads(z.read("results_v6c/CASE_"+case+"/"+arm+"/RESULT.json"))
   assert sha(baseline)==result["baseline_sarif_sha256"],("baseline compare",case,arm)
   assert result["baseline_total"]==next(x["baseline_warning_count"] for x in rpl.values() if x["case_id"]==case and x["condition"]=="P1"),("baseline count",case,arm)
assert cx.execute("SELECT COUNT(*) FROM arno_archive_vault_members WHERE role='PATCH'").fetchone()[0]==255
out=R/"mcp_uploads/jobs/arno_patch_reconciliation_v2/PREFLIGHT_EXTRA.json"
out.write_text(json.dumps({"status":"PASS","prompt_hashes_verified":21,"legacy_P1_hashes_verified":7,"AC_baseline_hashes_verified":12,"old_archive_patch_members":255},indent=2)+"\n")
print(out.read_text())
