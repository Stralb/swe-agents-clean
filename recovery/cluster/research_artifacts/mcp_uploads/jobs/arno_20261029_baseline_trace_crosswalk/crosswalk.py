#!/usr/bin/env python3
"""Read-only original Screen65 SARIF naming census and OWP14 trace mention audit.
Does NOT print any log content or secret-bearing path contents.
"""
import zipfile, re, json
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
P=R/"ARNO_CODEQL_EXPORT_20261019"
OUT=R/"mcp_uploads/jobs/arno_20261029_baseline_trace_crosswalk/REPORT.json"
CASES=["00668","03429","03581","06104","08152","08461","12344","15151","16633","20094","21682","22223","31207","32759"]
def cases_in(s):
 return [c for c in CASES if re.search(r"(?<![0-9])0*"+str(int(c))+r"(?![0-9])",s,re.I)]
def cls(n):
 t=n.lower()
 if not t.endswith(".sarif"):return None
 if "before" in t:return "BEFORE_NAME"
 if "after" in t:return "AFTER_NAME"
 return "SARIF_OTHER"
per=defaultdict(lambda:Counter())
examples=defaultdict(lambda:defaultdict(list))
count=Counter()
with zipfile.ZipFile(P/"05_SCREEN65_EVIDENCE.zip") as z:
 for m in z.infolist():
  tp=cls(m.filename)
  if not tp:continue
  count[tp]+=1
  for case in cases_in(m.filename):
   per[case][tp]+=1
   if len(examples[case][tp])<8:examples[case][tp].append(m.filename)
case_trace=defaultdict(lambda:Counter())
total_scanned=0
total_logs=0
with zipfile.ZipFile(P/"07_AGENT_PROMPTS_AND_TRACES.zip") as z:
 for m in z.infolist():
  n=m.filename.lower()
  if not n.endswith((".log",".jsonl",".json",".txt",".md")):continue
  if m.file_size>2000000:continue
  total_logs+=1
  candidates=cases_in(m.filename)
  if candidates:
   for c in candidates:case_trace[c]["filename_matches"]+=1
  # Count only masked case token occurrences in original logs, not raw contents.
  try:
   raw=z.read(m).decode("utf-8",errors="ignore")
  except Exception:continue
  total_scanned+=1
  for c in CASES:
   token="CASE_"+c
   if token in raw.upper():case_trace[c]["body_contains_explicit_case_token"]+=1
   elif re.search(r"(?<![0-9])0*"+str(int(c))+r"(?![0-9])",raw):
    case_trace[c]["body_contains_numeric_case_reference"]+=1
result={
 "utc":datetime.now(timezone.utc).isoformat(),
 "screen65_sarif_named_totals":dict(count),
 "owp14_case_screen65_named_counts":{c:dict(per[c]) for c in CASES},
 "owp14_screen65_sarif_name_examples":{c:dict(examples[c]) for c in CASES},
 "agent_trace_archive_scanned_members":total_scanned,
 "agent_trace_archive_candidate_members":total_logs,
 "agent_trace_case_references":{c:dict(case_trace[c]) for c in CASES},
 "limitations":[
 "File-name and log-text mentions are only discovery hints, not verified scanner baselines or authentic full agent trajectories.",
 "Screen65 and OWP14 belong to different experimental stages; never equate their baselines without repository commit and CodeQL version matching.",
 "No original trace/log content or credentials were emitted or extracted outside the archive."]
 }
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps({"status":"BASELINE_TRACE_DISCOVERY_COMPLETE",
 "sarif_named":dict(count),"per_case_baseline_candidates":{c:per[c]["BEFORE_NAME"] for c in CASES},
 "case_trace_references":result["agent_trace_case_references"],"report":str(OUT)},indent=2))
