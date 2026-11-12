#!/usr/bin/env python3
"""Audits original October experiment ZIPs, read-only SQLite and ZIP access.
Never alters master DB, invokes code or exports artifact contents.
"""
from pathlib import Path
from collections import Counter,defaultdict
import zipfile,re,hashlib,json,sqlite3,os,datetime
ROOT=Path.home()/"research_artifacts"
ARC=ROOT/"ARNO_CODEQL_EXPORT_20261019"
OUT=ROOT/"mcp_uploads/jobs/arno_oct28_rq3_evidence_audit/REPORT.json"
CASES=["00668","03429","03581","06104","08152","08461","12344","15151","16633","20094","21682","22223","31207","32759"]
files=["02_ALL_GENERATED_PATCHES.zip","03_CODEQL_SARIF_AND_SCANS.zip","04_FUNCTIONAL_TESTS_AND_TRIAGE.zip","07_AGENT_PROMPTS_AND_TRACES.zip"]
summary={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"archives":{},"patches_by_case":{},"scan_by_case":{},"warnings":[]}
member_index={}
for name in files:
 p=ARC/name
 with zipfile.ZipFile(p) as z:
  info=z.infolist()
  bad=z.testzip()
  member_index[name]=[x.filename for x in info]
  counter=Counter()
  for ent in info:
   low=ent.filename.lower()
   if low.endswith(".patch") or low.endswith(".diff"): counter["patches"]+=1
   elif low.endswith(".sarif"): counter["sarif"]+=1
   elif low.endswith(".json"):counter["json"]+=1
   elif low.endswith(".log"):counter["logs"]+=1
   elif low.endswith(".md"):counter["markdown"]+=1
   else:counter["other"]+=1
  summary["archives"][name]={"size":p.stat().st_size,"members":len(info),"crc_all_valid":bad is None,"bad_member":bad,"types":dict(counter)}
  if name=="02_ALL_GENERATED_PATCHES.zip":
   nested=[x for x in info if x.filename.endswith("all_case_patches_original.zip")]
   summary["archives"][name]["nested_patch_archive_count"]=len(nested)
   for ent in nested:
    if ent.file_size<10000000:
     import io
     with zipfile.ZipFile(io.BytesIO(z.read(ent))) as inner:
      xs=inner.namelist()
      summary["archives"][name]["nested_archive_patches"]=[x for x in xs if any(case in x for case in ("08461","15151"))]
      summary["archives"][name]["nested_archive_count"]=len(xs)
for case in CASES:
 summary["patches_by_case"][case]={}
 summary["scan_by_case"][case]={}
 for n in files:
  hits=[p for p in member_index[n] if (("CASE_"+case) in p or ("CASE_"+str(int(case))) in p)]
  for arm in ["O","W","P"]:
   patch=[p for p in hits if p.lower().endswith((".patch",".diff")) and re.search(r"CASE_"+case+r"[_/].*?"+arm+r"(?:[_./-]|$)",p,re.I)]
   if patch:summary["patches_by_case"][case][n+":"+arm]=patch
  sarif=[p for p in hits if p.lower().endswith(".sarif")]
  if sarif:summary["scan_by_case"][case][n]=sarif
summary["gaps"]={
 "no_standalone_O_patch":[c for c in CASES if not any(k.endswith(":O") for k in summary["patches_by_case"][c])],
 "no_scanner_sarif_in_export":[c for c in CASES if not summary["scan_by_case"][c]],
}
DB=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True);db.execute("PRAGMA query_only=ON")
tables=[r[0] for r in db.execute("select name from sqlite_master where type='table'")]
for t in ["arno_rq3_owp14_run_scans","arno_rq3_owp14_verified_patch_bytes","arno_rq3_owp14_original_artifacts","arno_recovered_agent_patch_bytes","arno_generated_patches","arno_experiment_runs","arno_experiment_scans"]:
 summary.setdefault("current_db_counts",{})[t]=db.execute('select count(*) from "'+t+'"').fetchone()[0] if t in tables else "NO_TABLE"
db.close()
OUT.parent.mkdir(parents=True,exist_ok=True)
if OUT.exists():raise RuntimeError("Report exists; refusing overwrite")
OUT.write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"status":"AUDIT_COMPLETE","result_file":str(OUT),"gaps":summary["gaps"],"archives":summary["archives"],"db":summary["current_db_counts"]},indent=2))
