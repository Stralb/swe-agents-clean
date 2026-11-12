"""Atomic, append-only import into existing 42 GB Arno research master. No Hugging Face writes."""
import datetime,hashlib,json,sqlite3,sys,zlib
from pathlib import Path
import ingest_prepare_v2 as p

ROOT=p.ROOT;STAGE=p.STAGE;MASTER=p.MASTER
R=p.RUNS;BASE=p.BASELINES
assert len(R)==21 and len(BASE)==7
assert MASTER.is_file()
conn=sqlite3.connect(str(MASTER),timeout=120,isolation_level=None)
conn.execute("PRAGMA foreign_keys=ON")
conn.execute("PRAGMA busy_timeout=120000")
before={
 "runs":conn.execute("SELECT COUNT(*) FROM arno_experiment_runs").fetchone()[0],
 "patches":conn.execute("SELECT COUNT(*) FROM arno_generated_patches").fetchone()[0],
 "scans":conn.execute("SELECT COUNT(*) FROM arno_experiment_scans").fetchone()[0],
 "master_bytes":MASTER.stat().st_size
}
stat={"runs":0,"patches":0,"scans":0,"metrics":0,"artifacts":0,"findings":0,"pending":0}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
DDL=[
"""CREATE TABLE IF NOT EXISTS arno_chat_codeql_metrics (
 run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 case_label TEXT NOT NULL, method TEXT NOT NULL,
 source_kind TEXT NOT NULL, source_tree_sha256 TEXT NOT NULL, source_zip_sha256 TEXT NOT NULL,
 baseline_total INTEGER NOT NULL, after_total INTEGER NOT NULL,
 new_vs_baseline INTEGER NOT NULL, historical_p1_new INTEGER NOT NULL,
 historical_p1_remaining INTEGER,
 codeql_version TEXT NOT NULL, codeql_suite TEXT NOT NULL, sarif_sha256 TEXT NOT NULL,
 patch_sha256 TEXT, receipt_status TEXT NOT NULL, functional_status TEXT NOT NULL,
 provenance_status TEXT NOT NULL, result_metadata_json TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS arno_chat_evidence_objects(
 artifact_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 role TEXT NOT NULL, source_locator TEXT NOT NULL,
 sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL,
 compression TEXT NOT NULL,content_zlib BLOB,verification_status TEXT NOT NULL,
 UNIQUE(run_id,role,sha256))""",
"""CREATE TABLE IF NOT EXISTS arno_chat_codeql_findings(
 finding_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 result_index INTEGER NOT NULL,rule_id TEXT NOT NULL,file_path TEXT NOT NULL,
 line INTEGER,column INTEGER,level TEXT,message TEXT NOT NULL,
 signature_sha256 TEXT NOT NULL,
 new_vs_baseline INTEGER NOT NULL CHECK(new_vs_baseline IN(0,1)),
 matches_historical_p1 INTEGER NOT NULL CHECK(matches_historical_p1 IN(0,1)),
 raw_result_json TEXT NOT NULL,
 UNIQUE(run_id,result_index))""",
"""CREATE TABLE IF NOT EXISTS arno_chat_pending_runs(
 run_id TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 method TEXT NOT NULL,status TEXT NOT NULL,agent_input_basename TEXT,
 missing_artifacts_json TEXT NOT NULL,notes TEXT)""",
"""CREATE TABLE IF NOT EXISTS arno_chat_ingest_ledger(
 batch_id TEXT PRIMARY KEY,ingested_utc TEXT NOT NULL,
 source_manifest_sha256 TEXT NOT NULL,completed_runs INTEGER NOT NULL,
 patch_count INTEGER NOT NULL,sarif_count INTEGER NOT NULL,
 finding_count INTEGER NOT NULL,missing_receipts_json TEXT NOT NULL,
 preexisting_counts_json TEXT NOT NULL,notes TEXT)""",
"CREATE INDEX IF NOT EXISTS arno_chat_f_rule_case ON arno_chat_codeql_findings(case_id,rule_id,new_vs_baseline)",
"CREATE INDEX IF NOT EXISTS arno_chat_f_run_new ON arno_chat_codeql_findings(run_id,new_vs_baseline)",
"CREATE INDEX IF NOT EXISTS arno_chat_m_case_method ON arno_chat_codeql_metrics(case_id,method)",
"CREATE INDEX IF NOT EXISTS arno_chat_artifacts_case_role ON arno_chat_evidence_objects(case_id,role)",
"""CREATE VIEW IF NOT EXISTS arno_v_chat_case_comparison AS
 SELECT case_label,case_id,run_id,method,source_kind,
 baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,
 functional_status,receipt_status,codeql_version,codeql_suite,sarif_sha256,patch_sha256,provenance_status
 FROM arno_chat_codeql_metrics""",
"""CREATE VIEW IF NOT EXISTS arno_v_chat_new_codeql_findings AS
 SELECT f.case_id,f.run_id,m.method,f.rule_id,f.file_path,f.line,f.message,
 f.signature_sha256,f.matches_historical_p1,f.raw_result_json
 FROM arno_chat_codeql_findings f JOIN arno_chat_codeql_metrics m ON m.run_id=f.run_id
 WHERE f.new_vs_baseline=1""",
"""CREATE VIEW IF NOT EXISTS arno_v_chat_artifact_inventory AS
 SELECT o.case_id,o.run_id,m.method,o.role,o.source_locator,o.sha256,o.original_bytes,
 o.compression,o.verification_status
 FROM arno_chat_evidence_objects o JOIN arno_chat_codeql_metrics m ON m.run_id=o.run_id"""
]
def add_artifact(cur,r,role,path,raw=None,expected=None,external=False):
 if external:
  assert path.is_file() and expected
  size=path.stat().st_size
  content=None;sha=expected;compression="EXTERNAL_ONLY";verification="VERIFIED_SHA256_EXTERNAL_PATH"
 else:
  if raw is None:raw=p.filebytes(path,expected)
  sha=p.sha(raw);size=len(raw)
  if expected:assert sha==expected,(r["id"],role)
  content=zlib.compress(raw,6);compression="zlib";verification="VERIFIED_SHA256_RAW_EMBEDDED"
 assert path.is_relative_to(ROOT),path
 locator=str(path.relative_to(ROOT))
 key=r["id"]+"::"+role
 cur.execute("""INSERT OR IGNORE INTO arno_chat_evidence_objects
   (artifact_id,run_id,case_id,role,source_locator,sha256,original_bytes,compression,content_zlib,verification_status)
   VALUES(?,?,?,?,?,?,?,?,?,?)""",(key,r["id"],r["case_int"],role,locator,sha,size,compression,content,verification))
 if cur.rowcount:stat["artifacts"]+=1
 else:
  ex=cur.execute("SELECT sha256,original_bytes,source_locator FROM arno_chat_evidence_objects WHERE artifact_id=?",(key,)).fetchone()
  assert ex==(sha,size,locator),("Existing artifact conflict",key,ex)

try:
 conn.execute("BEGIN IMMEDIATE")
 c=conn.cursor()
 for ddl in DDL:c.execute(ddl)
 found={row[0] for row in c.execute("SELECT id FROM cases WHERE id IN (3429,3581,8152,12344,22223,31207,32759)")}
 assert len(found)==7,found
 for r in R:
  rid=r["id"];cid=r["case_int"];case=r["case"]
  prompt_blob=p.filebytes(r["prompt"]) if r["prompt"] else None
  metadata=dict(r["meta"],chat_origin="ARNO_RESEARCH_STUFF_20261031",
      source_zip_sha256=r["source_sha"],source_zip_locator=str(r["source"].relative_to(ROOT)),
      baseline_total=len(BASE[case]["rows"]),
      recomputed_new_vs_baseline=r["new"],
      recomputed_historical_p1_new=r["historical_new"],
      historical_p1_remaining=r["historical_remaining"],
      receipt_status="PRESENT" if r["receipt"] else ("NOT_APPLICABLE" if r["method"]=="FROZEN_BASELINE" else "MISSING"))
  c.execute("""INSERT OR IGNORE INTO arno_experiment_runs
    (run_id,case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status)
    VALUES(?,?,?,?,?,?,?,?)""",(rid,cid,None,"OCT2026_ARCHITECTURAL_GENERATION",r["method"],prompt_blob,
        json.dumps(metadata,sort_keys=True),"CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED"))
  if c.rowcount:stat["runs"]+=1
  else:
   ex=c.execute("SELECT case_id,treatment FROM arno_experiment_runs WHERE run_id=?",(rid,)).fetchone()
   assert ex==(cid,r["method"]),("Run ID collision",rid,ex)
  if r["patch"]:
   patch=p.filebytes(r["patch"],r["meta"]["patch_sha256"])
   c.execute("""INSERT OR IGNORE INTO arno_generated_patches
    (patch_id,run_id,content_sha256,patch_blob,patch_uri,authenticity_status,notes)
    VALUES(?,?,?,?,?,?,?)""",(rid+"::PATCH",rid,p.sha(patch),patch,
       str(r["patch"].relative_to(ROOT)),
       "USER_RETURNED_PATCH_SHA_VERIFIED_GENERATOR_NOT_INDEPENDENTLY_ATTESTED",
       "Unmodified original returned patch, full byte content preserved"))
   if c.rowcount:stat["patches"]+=1
   else:
    ex=c.execute("SELECT content_sha256,length(patch_blob) FROM arno_generated_patches WHERE patch_id=?",(rid+"::PATCH",)).fetchone()
    assert ex==(p.sha(patch),len(patch)),("Patch conflict",rid)
  c.execute("""INSERT OR IGNORE INTO arno_experiment_scans
    (scan_id,run_id,scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified)
    VALUES(?,?,?,?,?,?,?,?)""",(rid+"::CODEQL",rid,"CodeQL",p.VERSION,None,
          r["sarif"],json.dumps(metadata,sort_keys=True),1))
  if c.rowcount:stat["scans"]+=1
  else:
   ex=c.execute("SELECT length(raw_result_blob),scanner_version,execution_verified FROM arno_experiment_scans WHERE scan_id=?",(rid+"::CODEQL",)).fetchone()
   assert ex==(len(r["sarif"]),p.VERSION,1),("Scanner conflict",rid,ex)
  receipt_status="PRESENT_VERIFIED" if r["receipt"] else ("NOT_APPLICABLE" if r["method"]=="FROZEN_BASELINE" else "MISSING")
  c.execute("""INSERT OR IGNORE INTO arno_chat_codeql_metrics
    (run_id,case_id,case_label,method,source_kind,source_tree_sha256,source_zip_sha256,
     baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,
     codeql_version,codeql_suite,sarif_sha256,patch_sha256,receipt_status,functional_status,
     provenance_status,result_metadata_json)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (rid,cid,case,r["method"],r["source_kind"],r["tree"],r["source_sha"],
     len(BASE[case]["rows"]),len(r["rows"]),r["new"],r["historical_new"],r["historical_remaining"],
     p.VERSION,p.SUITE,p.sha(r["sarif"]),r["meta"].get("patch_sha256"),
     receipt_status,r["functional"],"CODEQL_SHA_VERIFIED_FIRST_DELIVERY_FUNCTIONAL_UNVERIFIED",
     json.dumps(metadata,sort_keys=True)))
  if c.rowcount:stat["metrics"]+=1
  else:
   ex=c.execute("SELECT sarif_sha256,after_total,new_vs_baseline FROM arno_chat_codeql_metrics WHERE run_id=?",(rid,)).fetchone()
   assert ex==(p.sha(r["sarif"]),len(r["rows"]),r["new"]),("Metrics conflict",rid,ex)
  add_artifact(c,r,"baseline_sarif" if r["method"]=="FROZEN_BASELINE" else "after_sarif",
       r["sarif_path"],r["sarif"],p.sha(r["sarif"]))
  add_artifact(c,r,"result_json",r["dir"]/"RESULT.json")
  add_artifact(c,r,"source_zip_external",r["source"],expected=r["source_sha"],external=True)
  if r["patch"]:add_artifact(c,r,"patch",r["patch"],expected=r["meta"]["patch_sha256"])
  if r["receipt"]:add_artifact(c,r,"agent_receipt",r["receipt"],expected=r["meta"].get("receipt_sha256"))
  if r["prompt"]:add_artifact(c,r,"self_written_prompt",r["prompt"],prompt_blob,
                  r["meta"].get("prompt_sha256") or r["meta"].get("implementation_prompt_sha256"))
  if (r["dir"]/"warning_delta.json").is_file():
   add_artifact(c,r,"warning_delta_json",r["dir"]/"warning_delta.json")
  for name in ("analysis.log","analyze.log","codeql_analyze.log","create.log","db_create.log",
               "database_create.log","codeql_create.log","apply.log","apply_check.log",
               "version.log","codeql_version.log"):
   fp=r["dir"]/name
   if fp.is_file() and fp.stat().st_size<2500000:add_artifact(c,r,"log_"+name,fp)
  old_counts=p.counts(BASE[case]["rows"]).copy()
  hist_delta=r["p1_delta"].copy()
  for index,(key,line,column,level,raw_json) in enumerate(r["rows"]):
   new=0
   if r["method"]!="FROZEN_BASELINE":
    if old_counts[key]>0:old_counts[key]-=1
    else:new=1
   match=int(bool(new and hist_delta[key]>0))
   if match:hist_delta[key]-=1
   sig=p.sha(json.dumps(key,separators=(",",":"),ensure_ascii=False).encode())
   c.execute("""INSERT OR IGNORE INTO arno_chat_codeql_findings
    (finding_id,run_id,case_id,result_index,rule_id,file_path,line,column,level,message,
    signature_sha256,new_vs_baseline,matches_historical_p1,raw_result_json)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (rid+":"+str(index).zfill(6),rid,cid,index,key[0],key[1],line,column,level,key[2],sig,new,match,raw_json))
   if c.rowcount:stat["findings"]+=1
   else:
    ex=c.execute("SELECT signature_sha256,new_vs_baseline FROM arno_chat_codeql_findings WHERE finding_id=?",(rid+":"+str(index).zfill(6),)).fetchone()
    assert ex==(sig,new),("Finding conflict",rid,index)
  got=c.execute("SELECT COUNT(*),COALESCE(SUM(new_vs_baseline),0),COALESCE(SUM(matches_historical_p1),0) FROM arno_chat_codeql_findings WHERE run_id=?",(rid,)).fetchone()
  assert got[:2]==(len(r["rows"]),r["new"]),("Warning count mismatch",rid,got)
  if r["historical_remaining"] is not None:assert got[2]==r["historical_remaining"],(rid,got)
 for cid,rid in p.PENDING:
  input_name="ARNO_ARCHGEN_"+cid+"_ONE_CHAT_R1.zip"
  c.execute("""INSERT OR IGNORE INTO arno_chat_pending_runs
     (run_id,case_id,method,status,agent_input_basename,missing_artifacts_json,notes)
     VALUES(?,?,?,?,?,?,?)""",(rid,int(cid),"GENERAL_ARCHITECTURE","AWAITING_AGENT_OUTPUTS",input_name,
       json.dumps(["IMPLEMENTATION_PROMPT","PATCH","RECEIPT","POST_PATCH_SARIF"]),
       "Historical P1 and frozen baseline are already indexed; no ARCHGEN evaluation yet."))
  if c.rowcount:stat["pending"]+=1
 total=c.execute("SELECT COUNT(*) FROM arno_chat_codeql_metrics").fetchone()[0]
 findings=c.execute("SELECT COUNT(*) FROM arno_chat_codeql_findings").fetchone()[0]
 assert total==21 and findings==p.stats["individual_scanner_findings"],(total,findings)
 batch="ARNO_CHAT_EVIDENCE_20261031_R1"
 ledger_hash=p.sha(json.dumps(p.stats,sort_keys=True).encode())
 c.execute("""INSERT OR IGNORE INTO arno_chat_ingest_ledger
    (batch_id,ingested_utc,source_manifest_sha256,completed_runs,patch_count,sarif_count,
    finding_count,missing_receipts_json,preexisting_counts_json,notes)
    VALUES(?,?,?,?,?,?,?,?,?,?)""",
   (batch,now,ledger_hash,21,p.stats["patches"],21,findings,
    json.dumps(["ARCHGEN_22223_R1"]),json.dumps(before,sort_keys=True),
    "Append-only integration of seven baselines, seven P1 scans and seven interventions; two future ARCHGEN runs pending. Hugging Face untouched."))
 conn.commit()
except BaseException:
 conn.rollback()
 raise
finally:
 conn.close()
report={"status":"COMMIT_VERIFIED","master_path":str(MASTER),"committed_utc":now,
        "preexisting":before,"added":stat,"completed_scans":len(R),
        "all_codeql_findings":p.stats["individual_scanner_findings"],
        "pending_cases":p.PENDING,"missing_receipts":["ARCHGEN_22223_R1"],
        "cases":p.stats["case_summary"]}
dst=STAGE/"INGEST_RESULT.json"
assert not dst.exists()
dst.write_text(json.dumps(report,indent=2)+"\n")
print("MASTER_DB_IMPORT_COMMITTED",json.dumps({k:v for k,v in report.items() if k!="cases"},sort_keys=True),flush=True)
