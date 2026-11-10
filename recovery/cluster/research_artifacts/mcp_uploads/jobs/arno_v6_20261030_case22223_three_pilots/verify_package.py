#!/usr/bin/env python3
import hashlib,io,json,os,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots"
ready=ROOT/"ready"
manifest=json.loads((ROOT/"PILOT_MANIFEST_RESEARCHER_ONLY.json").read_text())
assert manifest["status"]=="THREE_COMPLETE_SOURCE_INCLUSIVE_PILOT_ZIPS_VERIFIED"
def sha(x):return hashlib.sha256(x).hexdigest()
records=[]
for row in manifest["packs"]:
 p=ready/row["file"]
 assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p.read_bytes())==row["sha256"]
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None and len([n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/")])==401
  if row["condition"]=="MECHANISM":continue
  report="REVIEW.json" if row["condition"]=="BLIND_REVIEW" else "PREDICTED_RISKS.json"
  field="findings" if report=="REVIEW.json" else "risks"
  spec=json.loads(z.read("STAGE2_SPEC.json"))
  assert spec["array"]==field and spec["report_name"]==report
  with tempfile.TemporaryDirectory(prefix="arno_pilot_selftest_") as d:
   d=Path(d);helper=d/"MAKE_STAGE2.py";helper.write_bytes(z.read("MAKE_STAGE2.py"))
   reportpath=d/"sample.json"
   reportdata={"run_id":spec["run_id"],field:[], "model":"SELFTEST_NOT_A_RESEARCH_OUTPUT","analysis_status":"SELFTEST"}
   raw=json.dumps(reportdata).encode()
   reportpath.write_bytes(raw)
   generated=d/"Stage2_SELFTEST_ONLY.zip"
   result=subprocess.run([str(Path.home()/"new/malicious-issue-miner-rate-smart/.venv/bin/python"),str(helper),str(p),str(reportpath),str(generated)],
     capture_output=True,text=True,check=False,timeout=150)
   assert result.returncode==0,(result.stdout,result.stderr)
   with zipfile.ZipFile(generated) as g:
    assert g.testzip() is None and g.read(report)==raw
    assert len([n for n in g.namelist() if n.startswith("REPO/") and not n.endswith("/")])==401
    assert g.read("ISSUE.md")==z.read("ISSUE.md")
    assert all(g.read(n)==z.read(n) for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/"))
    if row["condition"]=="BLIND_REVIEW":assert g.read("P1_PATCH.patch")==z.read("P1_PATCH.patch")
    else:assert "P1_PATCH.patch" not in g.namelist()
    assert "PROMPT.md" in g.namelist()
   records.append({"experiment":row["condition"],"selftest_status":"PASSED",
     "stage2_zip_generated":True,"source_files_unchanged":True,
     "dynamic_json_included_unchanged":True,"sensitive_prior_patch_visibility_correct":True})
note="""# ARNO 22223 - THREE SELF-CONTAINED PILOT EXPERIMENTS

EXTRACT this outer ZIP first. Upload only ONE of the three individual pilot ZIPs per new temporary chat.
In every temporary chat, add one message: Follow PROMPT.md inside the uploaded ZIP and return the requested downloadable artifacts.

A / MECHANISM: upload A ZIP to ONE new chat; download PATCH_PILOT22223_MECHANISM_R1.patch and RECEIPT_PILOT22223_MECHANISM_R1.json.
B / BLIND TWO-CHAT REVIEW: upload B ZIP to a NEW chat; download REVIEW_PILOT22223_BLIND_REVIEW_R1.json and ARNO_22223_B_STAGE2_REPAIR_READY.zip. Upload the returned Stage2 ZIP in a DIFFERENT NEW chat; download PATCH_PILOT22223_BLIND_REPAIR_R1.patch and RECEIPT_PILOT22223_BLIND_REPAIR_R1.json.
C / PROSPECTIVE TWO-CHAT PREDICTION: upload C ZIP to a NEW chat; download RISKS_PILOT22223_PROSPECTIVE_PREDICT_R1.json and ARNO_22223_C_STAGE2_IMPLEMENT_READY.zip. Upload the returned Stage2 ZIP in a DIFFERENT NEW chat; download PATCH_PILOT22223_PROSPECTIVE_BUILD_R1.patch and RECEIPT_PILOT22223_PROSPECTIVE_BUILD_R1.json.

B and C Stage1 ZIPs already include full Stage2 templates and MAKE_STAGE2.py, which the first chat must run with its actual report to produce the next-stage ZIP. DO NOT manually write the report into the next chat: the dynamic ZIP contains it.

Preserve ALL returned files, including JSON reports and generated Stage2 ZIPs. Return them together for independent CodeQL/functional analysis. Never show earlier scanner findings, RQ2 mechanism or other experimental arms to B/C.

Study design: A hindsight-derived RQ2 mechanism implementation; B blind review/repair of an existing P1 patch; C prospective risk prediction followed by fresh implementation. They do not share the same starting patch and must not be presented as causally equivalent. New warning counts and correctness are NOT yet known. Any BLOCKED outputs must be retained, not fabricated.
"""
bundle=ROOT/"ARNO_22223_THREE_READY_UPLOAD_PILOTS_20261030.zip"
assert not bundle.exists()
with zipfile.ZipFile(bundle,"w",zipfile.ZIP_DEFLATED,compresslevel=4) as z:
 for row in manifest["packs"]:
  p=ready/row["file"]
  z.write(p,"UPLOAD_THESE_INDIVIDUALLY/"+p.name)
 z.writestr("README_FIRST.md",note)
 z.write(ROOT/"PILOT_MANIFEST_RESEARCHER_ONLY.json","RESEARCHER_ONLY_MANIFEST_DO_NOT_UPLOAD.json")
 z.writestr("STAGE2_DRYRUN_VERIFICATION.json",json.dumps({"stage2_package_dry_runs":records},indent=2))
with zipfile.ZipFile(bundle) as z:
 assert z.testzip() is None and len(z.namelist())==6
assert len(records)==2
out={"status":"3_PILOT_ZIPS_AND_TWO_DYNAMIC_STAGE2_HANDOFFS_VERIFIED",
 "bundle_filename":bundle.name,"bundle_bytes":bundle.stat().st_size,
 "bundle_sha256":sha(bundle.read_bytes()),"initial_zip_count":3,
 "stage2_packaging_tests":records}
(ROOT/"FINAL_PACKAGING_REPORT.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2),flush=True)
