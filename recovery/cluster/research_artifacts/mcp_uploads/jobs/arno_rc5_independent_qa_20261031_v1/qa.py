#!/usr/bin/env python3
"""Independent release-candidate QA, no rewriting."""
import sqlite3,re,json,collections,hashlib,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
P=R/"mcp_uploads/jobs/arno_release_rc5_oct31/release/ARNO_REVIEWER_RC5_MINIMIZED.sqlite"
OUT=R/"mcp_uploads/jobs/arno_rc5_independent_qa_20261031_v1/output"
OUT.mkdir(parents=True,exist_ok=True)
db=sqlite3.connect("file:"+str(P)+"?mode=ro",uri=True,timeout=120)
db.row_factory=sqlite3.Row
hits=collections.Counter()
weird_schema=[]
private_values=[]
profanity=re.compile(r"(?i)\b(?:bullshit|incriminating|fake[- ]?review|cover[- ]?up|fabricated[- ]?data)\b")
internal=re.compile(r"(?i)(?:/home-mscluster/|/mnt/data/|C:\\Users\\|/Users/)")
sensitive=re.compile(r"(?i)(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9_]{20,}\b|\bsk-[A-Za-z0-9_-]{20,}\b)")
for name,type,sql in db.execute("SELECT name,type,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
 if re.search(r"(?i)peerreview|supervisor|recovery_v|handoff|mcp_uploads|20[12][0-9]{6}",name):
  weird_schema.append(name)
 if type!="table":continue
 cols=[x["name"] for x in db.execute('PRAGMA table_info("'+name+'")')]
 for idx,row in enumerate(db.execute('SELECT * FROM "'+name+'"'),1):
  for col,v in zip(cols,row):
   if isinstance(v,bytes):hits["BINARY_FIELD_BREACH"]+=1
   if not isinstance(v,str):continue
   for key,pattern in (("UNPROFESSIONAL_TEXT",profanity),("RAW_MACHINE_PATH",internal),("POTENTIAL_SECRET_OR_EMAIL",sensitive)):
    if pattern.search(v):
     hits[key]+=1
     private_values.append({"table":name,"column":col,"row_index":idx,"kind":key})
counts={}
keys={
"research_cases":"case_id","mined_findings":"finding_id","canonical_findings":"finding_id",
"experiment_runs":"run_id","patches":"patch_id","scan_executions":"scan_id",
"scan_findings":"finding_id","evidence_artifacts":"evidence_id","root_decisions":"root_id",
"human_review_labels":"review_id"}
for tab,key in keys.items():
 total=db.execute('SELECT COUNT(*) FROM "'+tab+'"').fetchone()[0]
 distinct=db.execute('SELECT COUNT(DISTINCT "'+key+'") FROM "'+tab+'"').fetchone()[0]
 counts[tab]={"rows":total,"unique_key_values":distinct,"duplicate_key_values":total-distinct}
a={
 "status":"INDEPENDENT_RC5_QA_COMPLETED",
 "source_sqlite_sha256":hashlib.sha256(P.read_bytes()).hexdigest(),
 "sqlite_quick_check":db.execute("PRAGMA quick_check").fetchone()[0],
 "schema_object_count":db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'").fetchone()[0],
 "schema_name_flags":weird_schema,"text_hits":dict(hits),
 "key_uniqueness":counts,
 "reviewer_disclosure_check":{"human_selected":db.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_ADJUDICATED'").fetchone()[0],
 "consensus_only":db.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='ALL_THREE_AGREE_NO_USER_VERDICT'").fetchone()[0],
 "deferred":db.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_DEFERRED'").fetchone()[0],
 "sensitive_payloads_excluded":db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND sql LIKE '%BLOB%'").fetchone()[0]==0},
 "limitations":"Limited regex/field-level scan, full external vault not scanned, artifact-level reproducibility not certified",
 "record_flags_not_excerpts":private_values,
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()
}
(OUT/"RC5_INDEPENDENT_QA.json").write_text(json.dumps(a,indent=2)+"\n")
assert a["sqlite_quick_check"]=="ok"
assert hits.get("BINARY_FIELD_BREACH",0)==0
print(json.dumps({"qa_status":a["status"],"hits":dict(hits),"weird_schema":weird_schema,"duplicate_counts":{k:v["duplicate_key_values"] for k,v in counts.items()}},indent=2))
db.close()
