#!/usr/bin/env python3
"""Read-only log-archive discovery for missing original O-arm patch evidence.
Looks only for case labels and patch markers; never exposes raw code, secrets,
prompts or full log content. No master writes or HF interaction.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import zipfile,re,json,hashlib
R=Path.home()/"research_artifacts"
ARCH=R/"ARNO_CODEQL_EXPORT_20261019"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_missing_o_patch_log_discovery/REPORT.json"
FILES=[
 "07_AGENT_PROMPTS_AND_TRACES.zip",
 "02_ALL_GENERATED_PATCHES.zip",
 "04_FUNCTIONAL_TESTS_AND_TRIAGE.zip",
 "06_EARLIER_CAUSAL_EXPERIMENTS.zip",
 "08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip"
]
CASES={"08461":[re.compile(r"CASE[_-]?0*8461",re.I),re.compile(r"(?<![0-9])08461(?![0-9])")],
       "15151":[re.compile(r"CASE[_-]?0*15151",re.I),re.compile(r"(?<![0-9])15151(?![0-9])")]}
DIFF=[re.compile(r"(?m)^diff --git ",re.I),
      re.compile(r"(?m)^--- a/.+$"),
      re.compile(r"(?m)^\+\+\+ b/.+$"),
      re.compile(r"(?i)\b(?:patch|diff) (?:file|generated|saved|written|contents)\b")]
summary={}
matched=[]
skipped=Counter()
for archive_name in FILES:
 p=ARCH/archive_name
 scanned=0
 with zipfile.ZipFile(p) as z:
  for member in z.infolist():
   if member.is_dir():continue
   if not member.filename.lower().endswith((".txt",".md",".json",".jsonl",".log",".out",".err",".patch",".diff",".csv",".tsv")):continue
   if member.file_size>5_000_000:
    skipped[archive_name]+=1
    continue
   try:raw=z.read(member)
   except (OSError,RuntimeError,zipfile.BadZipFile):continue
   scanned+=1
   text=raw.decode("utf-8",errors="replace")
   markers=[m.start() for pattern in DIFF for m in pattern.finditer(text)]
   for key,patterns in CASES.items():
    mentions=[m.start() for pattern in patterns for m in pattern.finditer(text)]
    if not mentions:continue
    min_dist=min((abs(a-b) for a in mentions for b in markers),default=None)
    result={
     "case_id":key,"archive":archive_name,
     "log_member_basename":Path(member.filename).name,
     "member_sha256":hashlib.sha256(raw).hexdigest(),
     "member_bytes":len(raw),
     "case_mentions":len(mentions),
     "patch_marker_hits":len(markers),
     "nearest_case_to_patch_marker_characters":min_dist,
     "discovery_grade":"CANDIDATE_ONLY" if min_dist is not None and min_dist<30000 else "CASE_MENTION_ONLY"
    }
    matched.append(result)
 summary[archive_name]={"text_members_scanned":scanned,
   "members_skipped_over_5mb":skipped[archive_name],
   "case_08461_member_hits":sum(x["archive"]==archive_name and x["case_id"]=="08461" for x in matched),
   "case_15151_member_hits":sum(x["archive"]==archive_name and x["case_id"]=="15151" for x in matched)}
matched.sort(key=lambda x:(x["discovery_grade"]!="CANDIDATE_ONLY",x["nearest_case_to_patch_marker_characters"] if x["nearest_case_to_patch_marker_characters"] is not None else 999999999,-x["case_mentions"]))
result={"status":"MISSING_O_PATCH_LOG_DISCOVERY_COMPLETE",
 "timestamp_utc":datetime.now(timezone.utc).isoformat(),
 "archives":summary,
 "candidate_summary":{key:{"log_members_mention_case":sum(x["case_id"]==key for x in matched),
 "log_members_have_patch_marker_near_case":sum(x["case_id"]==key and x["discovery_grade"]=="CANDIDATE_ONLY" for x in matched),
 "nearest_diff_marker_characters":min((x["nearest_case_to_patch_marker_characters"] for x in matched if x["case_id"]==key and x["nearest_case_to_patch_marker_characters"] is not None),default=None)} for key in CASES},
 "candidate_members":matched[:120],
 "limits":["Only case-token/diff-marker proximity is measured, not authenticity or exact original patch bytes.",
 "Archive members larger than 5MB are not scanned; nontext members are excluded.",
 "A log with a diff marker may refer to unrelated code or archival instructions.",
 "No original patch bytes were generated or reconstructed; database and Hugging Face unchanged."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps({"status":result["status"],"archives":summary,"candidate_summary":result["candidate_summary"],"closest":matched[:12],"report":str(OUT)},indent=2))
