#!/usr/bin/env python3
"""Emit safe internal manual-review queue for potential disclosure findings, no matched values."""
import sqlite3,re,zlib,csv,json
from pathlib import Path
from urllib.parse import quote
R=Path.home()/"research_artifacts"
src=R/"mcp_uploads/jobs/arno_reviewer_release_20261031_v3/output/ARNO_REVIEWER_RESTRICTED_CANDIDATE.sqlite"
OUT=R/"mcp_uploads/jobs/arno_reviewer_sensitive_review_queue_20261031_v1/results"
OUT.mkdir(parents=True,exist_ok=False)
con=sqlite3.connect("file:"+quote(str(src))+"?mode=ro",uri=True)
patterns={
"EMAIL_LIKE":r"(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}",
"PASSWORD_ASSIGNMENT_LIKE":r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{5,}['\"]",
"UNPROFESSIONAL_TERM":r"(?i)(?:incriminat|bullshit|hallucinat|fabricat(?:ed|ion)?|fake[_ -]?(?:data|result|review)|cover[_ -]?up)"
}
rg={k:re.compile(v) for k,v in patterns.items()}
items=[]
def scan(table,id,run,role,raw):
 if raw is None:return
 txt=raw.decode("utf-8","replace") if isinstance(raw,bytes) else str(raw)
 for typ,pat in rg.items():
  if pat.search(txt):
   items.append(dict(type=typ,source_table=table,source_record_id=id,run_id=run or "",role=role or "",text_size=len(txt),
    requires_manual_context_review="YES",raw_value_in_report="NO"))
for patch_id,run_id,body in con.execute("SELECT patch_id,run_id,patch_bytes FROM patches"):
 scan("patches",patch_id,run_id,"patch_bytes",body)
for evidence_id,run_id,role,encoding,content in con.execute("SELECT evidence_id,run_id,role,compression,compressed_evidence_bytes FROM evidence_artifacts"):
 if content is None or encoding!="zlib":continue
 try:
  decomp=zlib.decompressobj().decompress(content,8_000_001)
  if len(decomp)<=8_000_000:scan("evidence_artifacts",evidence_id,run_id,role,decomp)
 except Exception:continue
with (OUT/"MANUAL_REVIEW_QUEUE_NO_SECRETS.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(items[0]) if items else ["type","source_table","source_record_id","run_id","role","text_size","requires_manual_context_review","raw_value_in_report"])
 w.writeheader();w.writerows(items)
(OUT/"MANUAL_REVIEW_QUEUE_README.md").write_text("""# Manual review queue (restricted)

This queue identifies *where* risky-looking strings occurred, without exposing the matched text.
Items can be test examples, quotations, or true disclosures; no classification has been determined.
Inspect only in the secure research environment; retain original evidence and repair only the
publication-facing presentation, with a documented reason and source hashes.
This is not a full 42 GB evidence-vault scan.
""")
print(json.dumps({"status":"CREATED","rows":len(items),"category_counts":{k:sum(x["type"]==k for x in items) for k in patterns}},indent=2),flush=True)
