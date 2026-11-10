#!/usr/bin/env python3
"""Restricted candidate content hygiene audit (non-mutating); never emits secret values."""
import sqlite3,json,re,hashlib,zlib,collections
from pathlib import Path
from urllib.parse import quote
R=Path.home()/"research_artifacts"
db=R/"mcp_uploads/jobs/arno_reviewer_release_20261031_v3/output/ARNO_REVIEWER_RESTRICTED_CANDIDATE.sqlite"
OUT=R/"mcp_uploads/jobs/arno_reviewer_content_audit_20261031_v2/output"
OUT.mkdir(parents=True,exist_ok=False)
con=sqlite3.connect("file:"+quote(str(db))+"?mode=ro",uri=True)
con.execute("PRAGMA query_only=ON")
checks={
"email_address":r"(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}",
"credential_like_key":r"(?i)(?:AKIA[0-9A-Z]{16}|gh[pousr]_[a-z0-9]{25,}|hf_[a-z0-9]{25,}|sk-[a-z0-9]{24,})",
"private_key_block":r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
"password_assignment":r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{5,}['\"]",
"internal_names":r"(?i)(?:michael\s+pradel|professor|supervisor|peer[ _-]?review|internal[ _-]?audit|cluster[-_ ]job|/home-mscluster/|/mnt/data/)",
"unprofessional_wording":r"(?i)(?:incriminat|bullshit|hallucinat|fabricat(?:ed|ion)?|fake[_ -]?(?:data|result|review)|cover[_ -]?up)",
"validation_terms":r"(?i)(?:not[_ -]?verified|not[_ -]?validated|unverified|missing|incomplete|provisional|not[_ -]?uploaded)",
}
patterns={k:re.compile(v) for k,v in checks.items()}
counts=collections.Counter();by_field=collections.Counter();rows_scanned=collections.Counter();matches=[]
def examine(table,recid,field,value):
 if value is None:return
 if isinstance(value,bytes):
  content=value.decode("utf-8","replace")
 else:content=str(value)
 rows_scanned[table+"."+field]+=1
 cats=[]
 for category,rgx in patterns.items():
  hits=rgx.findall(content)
  if hits:
   counts[category]+=1
   by_field[table+"."+field+"::"+category]+=1
   cats.append(category)
 if cats:
  matches.append(dict(table=table,record_identifier_sha256=hashlib.sha256(str(recid).encode()).hexdigest()[:16],
   field=field,categories=cats,text_bytes=len(content.encode("utf-8","replace"))))
selection={
"experiment_runs":("run_id",["reproducibility_metadata"]),
"patches":("patch_id",["patch_bytes","original_patch_locator"]),
"scan_executions":("scan_id",["scanner_result_summary"]),
"scan_findings":("finding_id",["message","file_path"]),
"mined_findings":("finding_id",["description","file_path"]),
"canonical_findings":("finding_id",["description","file_path"]),
"archive_manifest":("sha256",["member_path","archive_name"]),
"classification_annotations":("case_id",["agent_tool","agent_provenance"]),
"control_reviews":("blind_id",["reason","review_provenance"]),
}
for table,(key,fields) in selection.items():
 cols=",".join([key]+fields)
 for row in con.execute("SELECT "+cols+" FROM "+table):
  for field,v in zip(fields,row[1:]):examine(table,row[0],field,v)
skip_by_compression=collections.Counter()
for eid,compression,raw in con.execute("SELECT evidence_id,compression,compressed_evidence_bytes FROM evidence_artifacts"):
 if raw is None:
  skip_by_compression[compression or "NONE"]+=1;continue
 if compression!="zlib":
  skip_by_compression[compression or "OTHER"]+=1;continue
 try:
  dec=zlib.decompressobj()
  content=dec.decompress(raw,8_000_001)
  if len(content)>8_000_000:
   skip_by_compression["DECOMPRESSED_OVER_8MB"]+=1;continue
  examine("evidence_artifacts",eid,"compressed_evidence_bytes",content)
 except Exception:
  skip_by_compression["DECOMPRESSION_ERROR"]+=1
report={
"scope":"RESTRICTED_CANDIDATE_TEXT_FIELDS_PATCHES_AND_ZLIB_EVIDENCE_ONLY; NOT_FULL_42GB_VAULT",
"status":"CONTENT_TRIAGE_COMPLETE_NOT_PRIVACY_CLEARED",
"excluded_from_results":"No actual credential/email strings or excerpts are emitted to the report",
"patterns":list(patterns),"counts_by_category":dict(counts),
"counts_by_table_field_category":dict(by_field),
"field_values_scanned":dict(rows_scanned),
"skipped_evidence":dict(skip_by_compression),
"flagged_record_fields":matches,
"interpretation":"Matches require manual contextual inspection; validation terms and scholarly reviewer discussion are not incriminating.",
"not_yet_complete":"Human annotation provenance, privacy policy and full original source/archive scan remain outstanding"
}
(OUT/"CONTENT_TRIAGE.json").write_text(json.dumps(report,indent=2)+"\n")
(OUT/"CONTENT_TRIAGE_SUMMARY.md").write_text(
"# Restricted reviewer candidate: content-hygiene scan\n\n"
"Scope: explicitly selected text fields, generated patches and embedded zlib evidence in compact reviewer candidate. "
"**Not a full vault scan** and **not a public clearance**.\n\n"+
"\n".join("- "+k+": "+str(counts[k])+" flagged field values" for k in checks)+"\n\n"
+"Any matching record needs manual contextual assessment, not automatic deletion or relabelling. "
+"Scientific limitations such as unverified reviews and negative findings must remain transparent.\n"
)
print(json.dumps({"status":"CONTENT_TRIAGE_COMPLETE","match_categories":dict(counts),"scanned_fields":sum(rows_scanned.values()),"skips":dict(skip_by_compression)},indent=2),flush=True)
con.close()
