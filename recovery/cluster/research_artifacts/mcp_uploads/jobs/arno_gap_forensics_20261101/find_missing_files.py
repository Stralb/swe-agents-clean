#!/usr/bin/env python3
"""Read-only bounded inventory of prior ARNO prompts/outputs; filenames and hashes only."""
from pathlib import Path
import os,json,zipfile,io,hashlib,time
R=Path.home()/"research_artifacts"
J=R/"mcp_uploads/jobs"
out=J/"arno_gap_forensics_20261101"
out.mkdir(parents=True,exist_ok=True)
dest=out/"FILENAME_AND_ARCHIVE_INVENTORY.json"
if dest.exists():raise FileExistsError("Refusing to overwrite")
targets=[
 R/"ARNO_CODEQL_EXPORT_20261019/07_AGENT_PROMPTS_AND_TRACES.zip",
 R/"ARNO_CODEQL_EXPORT_20261019/06_EARLIER_CAUSAL_EXPERIMENTS.zip",
 J/"arno_ac6_v6_20261030/ARNO_A_C_ALL12_EVIDENCE_INPUT.zip",
 J/"arno_ac6_v6_20261030/ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL_V6E.zip",
 J/"arno_v6_20261030_case22223_three_pilots/ARNO_22223_THREE_READY_UPLOAD_PILOTS_20261030.zip",
]
needle=("prompt","instructions","trajectory","transcript","risk","22223","03429","output","trace")
package=[]
for f in targets:
 if not f.is_file():package.append({"path":str(f),"status":"MISSING"});continue
 with zipfile.ZipFile(f) as z:
  names=z.namelist()
  matched=[n for n in names if any(k in n.lower() for k in needle)]
  obj={"path":str(f.relative_to(R)),"members":len(names),
   "matched_names":matched[:180],"sample_names":names[:25],
   "nested_zip_members":[n for n in names if n.lower().endswith(".zip")][:30]}
  if f.name.startswith("ARNO_22223_THREE_READY"):
   nested=[]
   for name in names:
    if not name.lower().endswith(".zip"):continue
    payload=z.read(name)
    if len(payload)>15000000:continue
    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
     innernames=inner.namelist()
     nested.append({"parent":name,"members":len(innernames),
      "prompt_names":[s for s in innernames if any(k in s.lower() for k in ("prompt","instruction","stage2"))][:60],
      "sample":innernames[:12]})
   obj["inner_zips"]=nested
  package.append(obj)
names=[]
for folder in [J,R/"prevention_pilot_phase2",R/"ARNO_CODEQL_EXPORT_20261019"]:
 if not folder.is_dir():continue
 counter=0
 for top,ds,fs in os.walk(folder):
  ds[:]=[d for d in ds if d not in ("node_modules",".git","__pycache__","codeql_db","database","db","cache","repos","repo","repo_after","repo_before")]
  for f in fs:
   counter+=1
   path=Path(top)/f
   low=str(path.relative_to(R)).lower()
   if any(s in low for s in ("pilot22223","case_22223","ac6","rpl7","prompt","conversation","trajectory","generation_trace","blind_review")) and path.suffix.lower() in (".json",".md",".txt",".zip",".log",".csv",".jsonl",".patch"):
    names.append(str(path.relative_to(R)))
  if counter>65000:break
 names.append({"scanned_under":str(folder.relative_to(R)),"files_examined":counter})
report={"status":"INVENTORY_ONLY","zip_packages":package,
 "candidate_file_paths":names[:1300],"candidates_total":len(names)}
dest.write_text(json.dumps(report,indent=2))
summary={"status":"PASS","candidate_paths":len(names),"packages":len(package),
 "pack_matched":[{"package":x.get("path"),"count":len(x.get("matched_names",[]))} for x in package]}
print(json.dumps(summary),flush=True)
