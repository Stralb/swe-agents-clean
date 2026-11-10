#!/usr/bin/env python3
"""Read-only content audit. Never prints or exports suspicious matched strings."""
import sqlite3,re,zlib,hashlib,json,csv,collections,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
S=R/"mcp_uploads/jobs/arno_d7_corrected_workbook_v4_20261031/output/ARNO_REVIEWER_WITH_CORRECTED_D7_ANNOTATIONS_V4_RELEASED.sqlite"
O=R/"mcp_uploads/jobs/arno_release_audit_20261031_v2/output"
O.mkdir(parents=True,exist_ok=True)
db=sqlite3.connect("file:"+str(S)+"?mode=ro",uri=True)
db.row_factory=sqlite3.Row
db.execute("PRAGMA query_only=ON")
patterns={
 "email":r"(?i)[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}",
 "key_header":r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
 "aws_access_key":r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
 "service_token":r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
 "password_assignment":r"""(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"\n]{5,}['"]""",
 "machine_path":r"(?i)(?:/home-mscluster/[\w/.\-]+|/mnt/data/[\w/.\-]+|/Users/[\w/.\-]+|C:\\Users\\[\w\\.\-]+)",
 "private_ipv4":r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
 "unprofessional_term":r"(?i)\b(?:bullshit|incriminating|cover[- ]?up|fake[- ]?review|fabricated[- ]?data)\b"
}
rx={k:re.compile(v) for k,v in patterns.items()}
table_counts=collections.Counter()
match_counts=collections.Counter()
scope=collections.Counter()
flags=[]
def check(t,col,id,text):
 if isinstance(text,bytes):text=text.decode("utf-8","replace")
 if not isinstance(text,str):return
 scope["fields_scanned"]+=1;scope["bytes_inspected"]+=len(text.encode("utf-8","replace"))
 found=[]
 for name,p in rx.items():
  if p.search(text):match_counts[name]+=1;table_counts[(t,col,name)]+=1;found.append(name)
 if found:flags.append(dict(table=t,column=col,record_key_hash=hashlib.sha256(str(id).encode()).hexdigest()[:20],flag_types="|".join(found)))
for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
 cur=db.execute('SELECT * FROM "'+t+'"')
 keys=[x[0] for x in cur.description]
 for i,row in enumerate(cur,1):
  id=str(row["run_id"]) if "run_id" in keys else str(row["case_id"]) if "case_id" in keys else str(i)
  for name,v in zip(keys,row):
   if isinstance(v,str):check(t,name,id,v)
   elif isinstance(v,bytes):
    if t=="evidence_artifacts" and name=="compressed_evidence_bytes":
     scope["zlib_objects"]+=1
     try:
      d=zlib.decompressobj();total=0;tail=""
      for off in range(0,len(v),32768):
       block=d.decompress(v[off:off+32768],64*1024*1024+1-total)
       total+=len(block)
       if total>64*1024*1024:
        scope["decompression_oversize"]+=1;break
       txt=tail+block.decode("utf-8","replace");check(t,name,id,txt);tail=txt[-200:]
      else:scope["zlib_completed"]+=1
     except (ValueError,zlib.error):
      scope["decompression_failed"]+=1
    else:scope["other_blob_fields"]+=1;check(t,name,id,v)
db.close()
out={"status":"RESTRICTED_FULL_V4_FIELD_CONTENT_TRIAGE_COMPLETE","time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"source_v4":str(S),"source_mutated":False,"counts_by_pattern":dict(match_counts),
"counts_by_table_column_pattern":{".".join(k):v for k,v in table_counts.items()},
"coverage":dict(scope),"flagged_field_occurrences":len(flags),
"limits":["Regex-only scanner is not a validated secret detector.","Zlib objects beyond 64 MiB excluded from complete inspection.","Original full 42 GB evidence vault and external-only source artifacts not covered.","Match may be harmless research/test content; manual verification required."]}
(O/"CONTENT_AUDIT.json").write_text(json.dumps(out,indent=2)+"\n")
with (O/"MANUAL_REVIEW_QUEUE_PRIVATE.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["table","column","record_key_hash","flag_types"]);w.writeheader();w.writerows(flags)
print(json.dumps({"status":"AUDIT_SUCCESS","patterns":out["counts_by_pattern"],"coverage":out["coverage"],"manual_flags":len(flags)},indent=2))
