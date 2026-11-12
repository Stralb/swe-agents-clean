#!/usr/bin/env python3
from pathlib import Path
import json,zipfile,hashlib,re
R=Path.home()/"research_artifacts"
S=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
P=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
O=R/"mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1"
O.mkdir(parents=True,exist_ok=True)
manifest=json.loads((S/"MANIFEST.json").read_text())
cases=[x for x in manifest["cases"] if x!="22223"]
rows=[]
for case in cases:
 record=next(x for x in manifest["runs"] if x["case_id"]==case and x["condition"]=="P1")
 archive=S/"run_zips"/(record["run_id"]+".zip")
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==record["sha256"]
 with zipfile.ZipFile(archive) as z:
  issue=z.read("ISSUE.md").decode("utf-8","replace")
  prompt=z.read("PROMPT.md").decode("utf-8","replace")
  repo=[p for p in z.namelist() if p.startswith("REPO/") and not p.endswith("/")]
 old=json.loads((P/("CASE_"+case)/record["run_id"]/"RESULT.json").read_text())
 pth=P/("CASE_"+case)/record["run_id"]/("PATCH_"+record["run_id"]+".patch")
 assert hashlib.sha256(pth.read_bytes()).hexdigest()==old["patch_sha256"]
 touched=re.findall(r"^diff --git a/(.+?) b/(.+?)$",pth.read_text(errors="replace"),flags=re.M)
 row={"case":case,"issue":issue,"original_prompt":prompt,"source_kind":record["source_kind"],"repo_file_count":len(repo),"source_zip_sha256":record["sha256"],"p1_id":record["run_id"],"p1_patch_sha256":old["patch_sha256"],"p1_modified_paths":touched,"p1_warnings_new":old.get("new_conservative_line_agnostic"),"p1_rules":old.get("new_conservative_by_rule"),"baseline_warnings":old.get("before_total")}
 (O/("CASE_"+case+"_RESEARCHER.json")).write_text(json.dumps(row,indent=2))
 rows.append({k:v for k,v in row.items() if k not in ("issue","original_prompt")})
(O/"INVENTORY.json").write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
