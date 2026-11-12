#!/usr/bin/env python3
"""Read-only, metadata-only archive provenance census.
No extraction to disk; no file contents, credentials, prompts or code emitted.
"""
from pathlib import Path
from collections import Counter,defaultdict
import zipfile,io,re,json,sqlite3,hashlib
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
BASE=R/"ARNO_CODEQL_EXPORT_20261019"
OUT=R/"mcp_uploads/jobs/arno_20261029_archive_provenance_audit/REPORT.json"
ARCHIVES=["01_ORIGINAL_OWP_INPUTS.zip","02_ALL_GENERATED_PATCHES.zip",
"03_CODEQL_SARIF_AND_SCANS.zip","04_FUNCTIONAL_TESTS_AND_TRIAGE.zip",
"05_SCREEN65_EVIDENCE.zip","06_EARLIER_CAUSAL_EXPERIMENTS.zip",
"07_AGENT_PROMPTS_AND_TRACES.zip","08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip",
"09_RESEARCH_CONCLUSIONS_AND_LIMITATIONS.zip"]
CASES=["00668","03429","03581","06104","08152","08461","12344","15151","16633","20094","21682","22223","31207","32759"]
def case_hits(name):
 s=name.upper()
 return [x for x in CASES if re.search(r'(?<![0-9])0*'+str(int(x))+r'(?![0-9])',s)]
def classify(n):
 v=n.lower()
 if v.endswith((".patch",".diff")):return "patch"
 if v.endswith(".sarif"):return "sarif"
 if v.endswith(".jsonl"):return "jsonl"
 if v.endswith(".json"):return "json"
 if v.endswith((".txt",".md")):return "text"
 if v.endswith((".log",".out",".err")):return "log"
 if v.endswith((".csv",".tsv")):return "tabular"
 if v.endswith((".zip",".tar.gz",".tgz")):return "nested_archive"
 return "other"
def safe_record(filename):
 # Only filename basename, no source contents; do not enumerate secrets.
 b=Path(filename).name
 return b if not any(x in b.lower() for x in (".env","token","secret","credential","key.pem","password")) else "[SENSITIVE_NAME_REDACTED]"
report={"utc":datetime.now(timezone.utc).isoformat(),"archives":{},"case_presence":{},
 "specific_missing_o_patch":{"08461":[],"15151":[]},"limits":[]}
per_case={c:defaultdict(Counter) for c in CASES}
for archive in ARCHIVES:
 p=BASE/archive
 with zipfile.ZipFile(p) as z:
  members=z.infolist()
  types=Counter();case_count=Counter();hits=[]
  nested_entries=[]
  for info in members:
   n=info.filename
   k=classify(n)
   types[k]+=1
   cases=case_hits(n)
   for c in cases:
    case_count[c]+=1
    per_case[c][archive][k]+=1
    if c in ("08461","15151") and ("_O" in n.upper() or "/O/" in n.upper()):
     if k=="patch":report["specific_missing_o_patch"][c].append({"archive":archive,"name":safe_record(n),"source":"outer"})
   if k=="nested_archive" and n.lower().endswith(".zip") and info.file_size<12000000:
    nested_entries.append(info)
   if (archive=="07_AGENT_PROMPTS_AND_TRACES.zip" and cases and
       k in ("jsonl","json","text","log") and len(hits)<30):
    hits.append({"case":cases,"basename":safe_record(n),"format":k})
  entry={"bytes":p.stat().st_size,"members":len(members),"file_types":dict(types),
     "case_name_matches":dict(case_count),"nested_zip_candidates":len(nested_entries)}
  if archive=="07_AGENT_PROMPTS_AND_TRACES.zip":
   entry["trace_name_samples"]=hits
   entry["sample_member_basenames"]=[safe_record(x.filename) for x in members[:30]]
  if archive=="03_CODEQL_SARIF_AND_SCANS.zip":
   entry["sarif_case_coverage"]={c:per_case[c][archive]["sarif"] for c in CASES}
   entry["before_name_count"]=sum("before" in m.filename.lower() and m.filename.lower().endswith(".sarif") for m in members)
   entry["after_name_count"]=sum("after" in m.filename.lower() and m.filename.lower().endswith(".sarif") for m in members)
  if archive=="02_ALL_GENERATED_PATCHES.zip":
   entry["patch_case_coverage"]={c:per_case[c][archive]["patch"] for c in CASES}
  nested=[]
  # Read only small nested ZIPs; no code/data execution and no inner content printing.
  for item in nested_entries[:80]:
   try:
    with zipfile.ZipFile(io.BytesIO(z.read(item))) as child:
     counter=Counter()
     for m in child.infolist():
      typ=classify(m.filename);counter[typ]+=1
      if typ=="patch":
       for c in case_hits(m.filename):
        if c in ("08461","15151") and ("_O" in m.filename.upper() or "/O/" in m.filename.upper()):
         report["specific_missing_o_patch"][c].append({"archive":archive,"name":safe_record(m.filename),"nested_zip":safe_record(item.filename),"source":"nested"})
     nested.append({"name":safe_record(item.filename),"member_count":len(child.infolist()),"types":dict(counter)})
   except (OSError,zipfile.BadZipFile,RuntimeError):
    nested.append({"name":safe_record(item.filename),"status":"unreadable_nested_zip"})
  if nested:entry["nested_zip_inventory"]=nested
  report["archives"][archive]=entry
report["case_presence"]={c:{a:dict(type_counts) for a,type_counts in info.items()} for c,info in per_case.items()}
report["limits"]=[
 "This is a filename/ZIP-index census, not a confirmation of agent trajectory authenticity or scientific validity.",
 "A name hit for a case does not prove the corresponding original prompt or patch exists.",
 "Some source artifacts may be inside non-ZIP nested archives or named without a case identifier.",
 "No secret, original prompt body, repository source code, patch content, or SARIF content was exposed."
]
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":"ARCHIVE_METADATA_AUDIT_COMPLETE","report":str(OUT),
"archive_member_totals":{k:v["members"] for k,v in report["archives"].items()},
"missing_o_patch_candidates":{k:len(v) for k,v in report["specific_missing_o_patch"].items()},
"agent_trace_archive":report["archives"]["07_AGENT_PROMPTS_AND_TRACES.zip"]},indent=2))
