#!/usr/bin/env python3
"""ARNO restricted raw-artifact disclosure-pattern screen, read-only DB.
No matched contents leave SQLite. Scan is not a secret detector or legal clearance.
"""
import sqlite3,re,hashlib,zlib,json,csv,zipfile,datetime,collections
from pathlib import Path
R=Path.home()/"research_artifacts"
DB=R/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
OUT=R/"mcp_uploads/jobs/arno_raw_disclosure_audit_20261031_v1/output"
OUT.mkdir(parents=True,exist_ok=True)
db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=180)
db.execute("PRAGMA query_only=ON")
spec=[
 ("arno_generated_patches","patch_blob","RAW_BYTES"),
 ("arno_rq3_owp14_verified_patch_bytes","patch_zlib","ZLIB"),
 ("arno_recovered_agent_patch_bytes","patch_zlib","ZLIB"),
 ("arno_chat_evidence_objects","content_zlib","ZLIB"),
 ("arno_experiment_scans","raw_result_blob","RAW_BYTES"),
 ("arno_rq3_codeql_screen65_original","result_zlib","ZLIB"),
 ("arno_rq3_owp14_run_scans","original_result_zlib","ZLIB"),
]
patterns={
 "EMAIL_LIKE":rb"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
 "PRIVATE_KEY_HEADER":rb"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
 "AWS_KEY":rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
 "TOKEN_LIKE":rb"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
 "PASSWORD_ASSIGNMENT":rb"""(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"\n]{5,}['"]""",
 "INTERNAL_MACHINE_PATH":rb"(?i)(?:/home-mscluster/[\w./\-]+|/mnt/data/[\w./\-]+|/Users/[\w./\-]+|C:\\Users\\[\w\\.\-]+)",
 "PRIVATE_IP_ADDRESS":rb"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.(?:\d{1,3}\.){2}\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
 "UNPROFESSIONAL_TERMS":rb"(?i)\b(?:bullshit|incriminating|fake[- ]?review|cover[- ]?up|fabricated[- ]?data)\b",
}
rx={n:re.compile(s) for n,s in patterns.items()}
limit=64*1024*1024
table_totals=collections.defaultdict(collections.Counter)
overall=collections.Counter()
triage=[]
def scan(table,key,raw,kind):
 rec=table_totals[table]
 rec["all_rows"]+=1
 if raw is None:
  rec["missing_blobs"]+=1
  return
 rec["blobs_scanned"]+=1
 rec["stored_bytes"]+=len(raw)
 if kind=="ZLIB":
  try:
   decomp=zlib.decompressobj()
   text=decomp.decompress(raw,limit+1)
   if len(text)>limit or decomp.unconsumed_tail:
    rec["oversize_uninspected"]+=1
    return
   text+=decomp.flush()
   rec["decompressed"]+=1
  except (zlib.error,ValueError,MemoryError):
   rec["decompression_failure"]+=1
   # Compressed bytes cannot be scanned meaningfully: record incomplete.
   return
 else:
  text=raw
  if len(text)>limit:
   rec["oversize_uninspected"]+=1
   return
 rec["inspected_bytes"]+=len(text)
 found={}
 for name,regex in rx.items():
  n=len(regex.findall(text))
  if n:
   overall[name]+=n
   rec["pattern_"+name]+=n
   found[name]=n
 if found:
  triage.append({"source_table":table,"rowid_sha256_prefix":hashlib.sha256(str(key).encode()).hexdigest()[:18],
                "flag_categories":";".join(sorted(found)),"occurrences":sum(found.values())})
for table,col,kind in spec:
 cur=db.execute('SELECT rowid,"'+col+'" FROM "'+table+'"')
 for rowid,raw in cur:
  if isinstance(raw,str):raw=raw.encode("utf-8","replace")
  scan(table,rowid,raw,kind)
# Annotation provenance is controlled separately; avoid printing source texts.
annotations={}
for table,cols in [("study_human_full_records",["source_flat_record_json","user_rationale_with_limitations","evidence_note"]),
 ("study_human_full_evidence",["evidence_text"]),("study_human_full_context",["source_context_json"])]:
 for col in cols:
  for rowid,v in db.execute('SELECT rowid,"'+col+'" FROM "'+table+'"'):
   scan(table+"."+col,rowid,v.encode("utf-8","replace") if isinstance(v,str) else v,"RAW_BYTES")
external_only=db.execute("SELECT COUNT(*) FROM study_artifacts WHERE storage_status='EXTERNAL_ONLY'").fetchone()[0]
report={
 "status":"RESTRICTED_RAW_ARTIFACT_PATTERN_SCAN_COMPLETE",
 "source_database":str(DB),
 "source_db_modified":False,
 "tables":{k:dict(v) for k,v in table_totals.items()},
 "pattern_occurrences":dict(overall),
 "flagged_records":len(triage),
 "external_only_evidence_references":external_only,
 "limits":[
  "Regex pattern hits are not confirmed credentials; inspect context manually.",
  "No original values or excerpts are exported in reports.",
  "This scan is restricted to seven core artifact BLOB families and human audit text; not the entire 42GB vault.",
  "External-only artifacts are not scanned.",
  "Uninspected compressed/oversized objects are disclosed in counts.",
  "Third-party licensing and right-to-redistribute are not established by technical scanning.",
  "A clean scan would not prove absence of sensitive information."
 ],
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "public_release_clearance":"NOT_CLEARED"
}
(OUT/"RAW_DISCLOSURE_SCAN.json").write_text(json.dumps(report,indent=2)+"\n")
with (OUT/"INTERNAL_TRIAGE_QUEUE_NO_EXCERPTS.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["source_table","rowid_sha256_prefix","flag_categories","occurrences"])
 w.writeheader();w.writerows(triage)
(OUT/"README_PRIVATE.md").write_text("""# ARNO restricted disclosure-pattern scan
This is a private triage receipt, not permission to distribute source code or a declaration that no secrets exist.
It scanned embedded patch bodies, O/W/P historical patch and SARIF records, recovered agent patches, original scanner reports, compressed evidence, and the preserved human annotation text.
No matched strings were exported. Triage records contain hashed row IDs and category counts only.
The 42GB source vault, external-only artifacts, copyright/licence scope and other unstructured data still require separate review. The full master and unified source database were not modified.
""")
with zipfile.ZipFile(OUT/"ARNO_RESTRICTED_RAW_DISCLOSURE_TRIAGE.zip","w",zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for name in ["RAW_DISCLOSURE_SCAN.json","INTERNAL_TRIAGE_QUEUE_NO_EXCERPTS.csv","README_PRIVATE.md"]:
  z.write(OUT/name,name)
assert zipfile.ZipFile(OUT/"ARNO_RESTRICTED_RAW_DISCLOSURE_TRIAGE.zip").testzip() is None
print(json.dumps({"status":report["status"],"flagged_records":len(triage),
 "pattern_occurrences":dict(overall),"external_refs":external_only,
 "scanned_tables":len(table_totals),"triage_zip_bytes":(OUT/"ARNO_RESTRICTED_RAW_DISCLOSURE_TRIAGE.zip").stat().st_size},indent=2),flush=True)
db.close()
