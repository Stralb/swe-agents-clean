#!/usr/bin/env python3
"""Inspect original output indexes for two missing O-arm patch slots.
No raw prompt, code, warning text, or private file contents printed.
"""
from pathlib import Path
from collections import Counter
import zipfile,csv,io,re,json,hashlib
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
BASE=R/"ARNO_CODEQL_EXPORT_20261019"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_missing_o_original_index_audit/REPORT.json"
ARCHIVES=["02_ALL_GENERATED_PATCHES.zip","03_CODEQL_SARIF_AND_SCANS.zip",
"04_FUNCTIONAL_TESTS_AND_TRIAGE.zip","06_EARLIER_CAUSAL_EXPERIMENTS.zip"]
CASES=["08461","15151"]
pattern=re.compile(r"CASE[_-]?0*(8461|15151)(?![0-9])",re.I)
keep=re.compile(r"(?:^|_)(?:status|state|result|outcome|success|failure|missing|exists|generated|validated|arm|condition|case_id|case|source_type|patch_count|patch_sha256|reason_code)(?:$|_)",re.I)
bycase={c:[] for c in CASES}
inventory=[]
for arc in ARCHIVES:
 p=BASE/arc
 with zipfile.ZipFile(p) as z:
  for member in z.infolist():
   name=Path(member.filename).name
   if not name.lower().endswith(".csv"):continue
   if "index" not in name.lower() and "result" not in name.lower() and "summary" not in name.lower():continue
   if member.file_size>2_000_000:continue
   raw=z.read(member)
   try:
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig","replace")))
    if not reader.fieldnames:continue
    header=reader.fieldnames
    counts=Counter();selected={c:[] for c in CASES}
    for row in reader:
     line=" ".join(str(v or "") for v in row.values())
     matches={("08461" if m=="8461" else "15151") for m in pattern.findall(line)}
     for case in matches:
      counts[case]+=1
      if len(selected[case])<14:
       projected={}
       for k,v in row.items():
        if not k or not keep.search(k):continue
        value=str(v or "")
        if len(value)>130 or "\n" in value:projected[k]={"sha256":hashlib.sha256(value.encode()).hexdigest(),"chars":len(value)}
        else:projected[k]=value
       selected[case].append(projected)
   except (ValueError,csv.Error):continue
   if not any(counts.values()):continue
   inventory.append({"archive":arc,"index_member_basename":name,"columns":header[:55],"matched_rows":dict(counts)})
   for c in CASES:
    if counts[c]:
     bycase[c].append({"archive":arc,"index_member_basename":name,"matched_row_count":counts[c],
      "selected_metadata_rows":selected[c]})
report={"status":"MISSING_O_GENERATION_INDEX_AUDIT_COMPLETE","utc":datetime.now(timezone.utc).isoformat(),
 "case_indexes":bycase,"matched_index_files":inventory,
 "limitations":["Rows matching case IDs may refer to W/P arms or different experiment phases.",
 "Status fields reflect archived indexes and do not authenticate an original generated O patch.",
 "No raw patches were reconstructed or inserted into the database."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":report["status"],"case_counts":{k:len(v) for k,v in bycase.items()},
 "index_files":[{"archive":x["archive"],"member":x["index_member_basename"],"matched_rows":x["matched_rows"]} for x in inventory],
 "case_sample":{k:[{"archive":v["archive"],"member":v["index_member_basename"],"rows":v["selected_metadata_rows"][:3]} for v in entries[:4]] for k,entries in bycase.items()}},indent=2))
