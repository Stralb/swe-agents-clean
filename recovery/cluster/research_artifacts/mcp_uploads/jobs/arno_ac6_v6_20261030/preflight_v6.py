#!/usr/bin/env python3
from pathlib import Path
import ast,hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
S=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
rows=[]
m=json.loads((S/"MANIFEST.json").read_text())
for case in ["03429","03581","08152","12344","31207","32759"]:
 p1=next(x for x in m["runs"] if x["case_id"]==case and x["condition"]=="P1")
 src=S/"run_zips"/(p1["run_id"]+".zip")
 b=B/("CASE_"+case)/"baseline.sarif"
 o=P/("CASE_"+case)/p1["run_id"]/"after.sarif"
 rows.append({"case_id":case,"source_exists":src.is_file(),"source_bytes":src.stat().st_size if src.exists() else None,
              "baseline_exists":b.is_file(),"original_p1_sarif_exists":o.is_file(),"source_kind":p1["source_kind"]})
for n in ["scan_ac_v6b.py","unpack.py"]:
 ast.parse((D/n).read_text(),filename=n)
status={"script_syntax_valid":True,"cases":rows,
 "uploaded_evidence_zip_exists":(D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip").exists(),
 "ready_for_upload":all(r["source_exists"] and r["baseline_exists"] and r["original_p1_sarif_exists"] for r in rows)}
(D/"PREFLIGHT_V6.json").write_text(json.dumps(status,indent=2))
print(json.dumps(status,indent=2),flush=True)
