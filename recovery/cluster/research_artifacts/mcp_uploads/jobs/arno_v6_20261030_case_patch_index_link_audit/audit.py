#!/usr/bin/env python3
"""Locate case-level original patch references without conflating with O arm.
Only harmless index field names, status strings, path basenames and file hashes
are written. No prompts, code, issue text, SARIF or secrets copied.
"""
from pathlib import Path
import zipfile,csv,io,re,json,hashlib
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
Z=R/"ARNO_CODEQL_EXPORT_20261019/02_ALL_GENERATED_PATCHES.zip"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_case_patch_index_link_audit/REPORT.json"
CASES=["08461","15151"]
def match(case,s):
 return re.search(r"CASE[_-]?0*"+str(int(case))+r"(?![0-9])",s or "",re.I) is not None
with zipfile.ZipFile(Z) as z:
 hits=[i for i in z.infolist() if Path(i.filename).name=="RESULTS_INDEX_ORIGINAL.csv"]
 assert len(hits)==1
 raw=z.read(hits[0])
 reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig","replace")))
 columns=reader.fieldnames or []
 found={case:[] for case in CASES}
 for row in reader:
  val=str(row.get("case_id","") or "")
  for case in CASES:
   if not match(case,val):continue
   attrs={}
   for key,value in row.items():
    if key is None:continue
    v=str(value or "")
    lower=key.lower()
    if re.search(r"(?:secret|token|credential|password|key_material|prompt_text|patch_text|diff_text|issue_body|result_body)",lower):continue
    if re.search(r"(?:path|file|artifact|output|input|script|source|log)",lower):
     attrs[key]={"basename":Path(v).name if v else None,"present":bool(v)}
    elif re.search(r"(?:status|state|condition|arm|model|sha256|hash|reason|error|success|run|attempt)",lower):
     attrs[key]=v if len(v)<=120 and "\n" not in v else {"chars":len(v),"sha256":hashlib.sha256(v.encode()).hexdigest()}
   found[case].append({"metadata_fields":attrs,"row_sha256":hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()})
 patch_files={case:[] for case in CASES}
 for m in z.infolist():
  if m.is_dir() or not m.filename.lower().endswith((".patch",".diff")):continue
  for case in CASES:
   if match(case,m.filename):
    patch_files[case].append({"member_basename":Path(m.filename).name,
      "size":m.file_size,"path_has_o_arm_label":bool(re.search(r"CASE[_-]?0*"+str(int(case))+r"[_-]O(?![A-Z0-9])",m.filename,re.I))})
result={"status":"ORIGINAL_CASE_PATCH_INDEX_LINK_AUDIT_COMPLETE",
 "utc":datetime.now(timezone.utc).isoformat(),
 "source_file":"02_ALL_GENERATED_PATCHES.zip:RESULTS_INDEX_ORIGINAL.csv",
 "original_index_fields":columns,
 "case_records":found,"case_named_patch_file_inventory":patch_files,
 "summary":{case:{"index_rows":len(found[case]),
   "case_named_patch_members":len(patch_files[case]),
   "case_named_explicit_o_arm_patch_members":sum(x["path_has_o_arm_label"] for x in patch_files[case])} for case in CASES},
 "limits":["Case-level patched status is NOT proof of a later O-arm generated patch.",
          "File names alone do not prove original generation authenticity.",
          "No raw patch or sensitive text extracted."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps({"status":result["status"],"summary":result["summary"],
 "index_fields":columns,"case_index_metadata":found},indent=2))
