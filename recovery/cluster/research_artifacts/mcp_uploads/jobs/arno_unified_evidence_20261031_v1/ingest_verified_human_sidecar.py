#!/usr/bin/env python3
"""Add corrected human rationale, 227 evidence rows and exact workbook bytes
to the NEW unified 42GB database only, after the sidecar is transferred.
No changes to the original Wits master, V4 reviewer source, or sidecar.
"""
from pathlib import Path
import sqlite3,hashlib,json,datetime
base=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
target=base/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
sidecar=base/"ARNO_D7_CORRECTED_REVIEW_SIDECAR.sqlite"
EXPECTED_SHA="b10f19f002f0447f6816d95aff9808e9cb53a6633750b560e7bc513682733e74"
WORKBOOK_SHA="e2370e44b64a051db061642e271e671310fba19969af24421291214fa339925e"
assert (base/"UNIFIED_VALIDATION.json").exists(),"Full unified DB has not completed source reconciliation"
assert target.exists() and sidecar.exists(),"Source-sidecar not transferred to Wits output directory"
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as stream:
  for chunk in iter(lambda: stream.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
assert sha(sidecar)==EXPECTED_SHA,"Sidecar digest mismatch: DO NOT INGEST"
source=sqlite3.connect("file:"+str(sidecar)+"?mode=ro",uri=True)
source.row_factory=sqlite3.Row
assert source.execute("PRAGMA quick_check").fetchone()[0]=="ok"
counts={}
for name,count in [
 ("human_review_batches",1),("human_annotation_records",50),
 ("human_annotation_supporting_evidence",227),
 ("human_annotation_evidence_context",50),
 ("annotation_workbook_original_bytes",1),
 ("annotation_revision_provenance",1)]:
 n=source.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0]
 assert n==count,(name,n,count)
 counts[name]=n
assert source.execute("SELECT source_sha256 FROM human_review_batches").fetchone()[0]==WORKBOOK_SHA
book=source.execute("SELECT raw_xlsx,source_sha256 FROM annotation_workbook_original_bytes").fetchone()
assert hashlib.sha256(book[0]).hexdigest()==book[1]==WORKBOOK_SHA
db=sqlite3.connect(str(target),timeout=180)
db.row_factory=sqlite3.Row
db.execute("PRAGMA foreign_keys=ON")
assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='study_human_full_records'").fetchone(),"Already imported; no overwrites"
assert db.execute("SELECT COUNT(*) FROM study_human_reviews").fetchone()[0]==50
baseline={
 r["review_id"]:(r["root_id"],r["case_id"],r["status"],r["selected_route"],r["selected_tier"])
 for r in db.execute("SELECT review_id,root_id,case_id,status,selected_route,selected_tier FROM study_human_reviews")}
for r in source.execute("""SELECT review_id,root_id,case_id,verdict_status,
human_selected_route,human_selected_tier FROM human_annotation_records"""):
 assert baseline[r["review_id"]]==(r["root_id"],r["case_id"],r["verdict_status"],r["human_selected_route"],r["human_selected_tier"]),("LABEL_MISMATCH",r["review_id"])
# Use named typed tables, preserve raw verbatim JSON text and reasoning.
db.executescript("""
CREATE TABLE study_human_full_records(
 review_id TEXT PRIMARY KEY REFERENCES study_human_reviews(review_id),
 batch_id TEXT NOT NULL,source_flat_record_json TEXT NOT NULL,
 source_flat_record_sha256 TEXT NOT NULL,
 user_rationale_with_limitations TEXT,caveat_flags TEXT,evidence_note TEXT,
 issue_url TEXT,source_diff_url TEXT,source_checked_status TEXT,
 source_review_attribution TEXT NOT NULL,provenance_class TEXT NOT NULL);
CREATE TABLE study_human_full_evidence(
 review_id TEXT NOT NULL REFERENCES study_human_reviews(review_id),
 evidence_ordinal INTEGER NOT NULL,case_id INTEGER,
 evidence_type TEXT,identifier TEXT,rule_id TEXT,scanner TEXT,
 source_path TEXT,source_line TEXT,evidence_text TEXT,
 scope_caveat TEXT,original_sheet TEXT,
 PRIMARY KEY(review_id,evidence_ordinal));
CREATE TABLE study_human_full_context(
 review_id TEXT PRIMARY KEY REFERENCES study_human_reviews(review_id),
 source_context_json TEXT NOT NULL);
CREATE TABLE study_human_workbook_original(
 source_sha256 TEXT PRIMARY KEY,source_filename TEXT NOT NULL,
 source_length INTEGER NOT NULL,raw_xlsx BLOB NOT NULL);
CREATE TABLE study_human_sidecar_manifest(
 source_sha256 TEXT PRIMARY KEY,source_file_sha256 TEXT NOT NULL,
 records_count INTEGER NOT NULL,evidence_count INTEGER NOT NULL,
 contextual_records INTEGER NOT NULL,source_revision_json TEXT NOT NULL,
 provenance_note TEXT NOT NULL);
""")
db.execute("BEGIN IMMEDIATE")
for r in source.execute("SELECT * FROM human_annotation_records"):
 db.execute("INSERT INTO study_human_full_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 r["review_id"],r["batch_id"],r["source_flat_record_json"],r["source_flat_record_sha256"],
 r["user_rationale_with_limitations"],r["caveat_flags"],r["evidence_note"],
 r["issue_url"],r["source_diff_url"],r["source_checked_status"],
 r["source_review_attribution"],r["provenance_class"]))
for r in source.execute("SELECT * FROM human_annotation_supporting_evidence"):
 db.execute("INSERT INTO study_human_full_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 r["review_id"],r["evidence_ordinal"],r["case_id"],r["evidence_type"],
 r["identifier"],r["rule_id"],r["scanner"],r["source_path"],
 r["source_line"],r["evidence_text"],r["scope_caveat"],r["original_sheet"]))
for r in source.execute("SELECT * FROM human_annotation_evidence_context"):
 db.execute("INSERT INTO study_human_full_context VALUES(?,?)",(r["review_id"],json.dumps(dict(r),ensure_ascii=False,sort_keys=True)))
r=source.execute("SELECT source_sha256,source_filename,source_length,raw_xlsx FROM annotation_workbook_original_bytes").fetchone()
db.execute("INSERT INTO study_human_workbook_original VALUES(?,?,?,?)",tuple(r))
revision=source.execute("SELECT * FROM annotation_revision_provenance").fetchone()
db.execute("INSERT INTO study_human_sidecar_manifest VALUES(?,?,?,?,?,?,?)",(
 WORKBOOK_SHA,EXPECTED_SHA,50,227,50,json.dumps(dict(revision),ensure_ascii=False,sort_keys=True),
 "41 POST-HOC AI-ASSISTED HUMAN-SELECTED; 8 CONSENSUS-ONLY; 1 DEFERRED; NO INDEPENDENT HUMAN-HUMAN RELIABILITY"))
assert db.execute("SELECT COUNT(*) FROM study_human_full_records").fetchone()[0]==50
assert db.execute("SELECT COUNT(*) FROM study_human_full_evidence").fetchone()[0]==227
assert db.execute("SELECT COUNT(*) FROM study_human_full_context").fetchone()[0]==50
assert db.execute("SELECT COUNT(*) FROM study_human_full_records WHERE user_rationale_with_limitations IS NOT NULL AND LENGTH(TRIM(user_rationale_with_limitations))>0").fetchone()[0]==42
assert db.execute("PRAGMA foreign_key_check('study_human_full_records')").fetchall()==[]
assert db.execute("PRAGMA foreign_key_check('study_human_full_evidence')").fetchall()==[]
db.commit();source.close();db.close()
report={"status":"CORRECTED_HUMAN_FULL_SOURCE_INGESTED",
 "source_sidecar_sha256":EXPECTED_SHA,"workbook_sha256":WORKBOOK_SHA,
 "records":50,"supporting_evidence":227,"context_rows":50,
 "original_workbook_bytes_preserved":True,"review_provenance":"POST_HOC_AI_ASSISTED_NOT_INDEPENDENT_BLIND",
 "source_master_unchanged":True,"target_only":str(target),
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
(base/"HUMAN_SIDECAR_IMPORT_VERIFIED.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
