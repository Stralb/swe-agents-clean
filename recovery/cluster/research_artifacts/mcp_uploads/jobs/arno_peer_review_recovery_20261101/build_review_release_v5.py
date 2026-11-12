#!/usr/bin/env python3
"""ARNO v5 verified addon. Non-destructive corrected copy of verified replay v3.
Original 42GB SQLite is attached for external analysis, never modified.
"""
import sqlite3,json,zlib,hashlib,shutil,os
from pathlib import Path
ROOT=Path.home()/"research_artifacts"
J=ROOT/"mcp_uploads/jobs"
ORIGINAL=J/"arno_replay_sidecar_v3_20261101/output_local_v5_79739/ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite"
PROOF=J/"arno_peer_review_recovery_20261101/proof/ARCHIVE_ONLY_150_SHA256_VERIFIED.sqlite"
PARENT_SHA="7caa56a892f657d888ed99ce7e8e84ada12ddbb7fd504929b3c69097657a1629"
PROOF_SHA="0b53ca511562b3792118ebf0a8401f6707e8c8abf47faf51547c3132b40de239"
OUT=J/"arno_peer_review_recovery_20261101/final_v5"
OUT.mkdir(parents=True,exist_ok=True)
FINAL=OUT/"ARNO_REPLAY_EVIDENCE_v5_ARCHIVES_AND_CORRECTIONS.sqlite"
PART=OUT/"ARNO_REPLAY_EVIDENCE_v5_ARCHIVES_AND_CORRECTIONS.sqlite.partial"
QA=OUT/"RELEASE_V5_QA.json"
assert not FINAL.exists() and not PART.exists() and not QA.exists()
def digest(data):return hashlib.sha256(data).hexdigest()
def filehash(file):
 h=hashlib.sha256()
 with open(file,"rb") as f:
  for part in iter(lambda:f.read(4*1024*1024),b""):h.update(part)
 return h.hexdigest()
assert filehash(ORIGINAL)==PARENT_SHA and filehash(PROOF)==PROOF_SHA
src=sqlite3.connect("file:"+str(ORIGINAL)+"?mode=ro",uri=True)
db=sqlite3.connect(str(PART));src.backup(db);src.close()
db.executescript("""
ALTER TABLE arno_v3_run_evidence ADD COLUMN source_zip_sha256 TEXT;
ALTER TABLE arno_v3_run_evidence ADD COLUMN input_zip_verification_status TEXT;
CREATE TABLE arno_v5_archive_raw_patches(
archive_name TEXT,member_path TEXT,case_id TEXT,sha256 TEXT,original_bytes INTEGER,
zlib_blob BLOB,verified INTEGER,PRIMARY KEY(archive_name,member_path));
CREATE TABLE arno_v5_correction_ledger(
run_id TEXT,field TEXT,previous_value TEXT,new_value TEXT,
source_evidence_sha256 TEXT,verified_physical_zip INTEGER,
reason TEXT,PRIMARY KEY(run_id,field));
CREATE TABLE arno_v5_reproducibility(
run_id TEXT PRIMARY KEY,codeql_version TEXT,scanner_suite TEXT,
exact_prompt_embedded INTEGER,independent_functional_test INTEGER,
independent_agent_attestation INTEGER,source_kind TEXT);
CREATE TABLE arno_v5_release_info(key TEXT PRIMARY KEY,value TEXT);
CREATE VIEW arno_v5_cohort_summary AS
SELECT cohort,arm,COUNT(*) AS runs,SUM(introduced_count) AS codeql_new_warnings
FROM arno_v3_run_evidence GROUP BY cohort,arm;
""")
proof=sqlite3.connect("file:"+str(PROOF)+"?mode=ro",uri=True)
arr=proof.execute("SELECT archive,member,case_id,sha256,bytes,compressed_blob,verified FROM archive_only_patch").fetchall()
assert len(arr)==150
for ar,member,case,h,n,blob,verified in arr:
 original=zlib.decompress(blob)
 assert verified==1 and len(original)==n and digest(original)==h
 row=db.execute("SELECT patch_sha256,original_bytes,indexed_in_master FROM arno_v3_archive_crosswalk WHERE archive_name=? AND member_path=?",(ar,member)).fetchone()
 assert row and row==(h,n,0),(ar,member,"crosswalk mismatch")
 db.execute("INSERT INTO arno_v5_archive_raw_patches VALUES(?,?,?,?,?,?,?)",(ar,member,case,h,n,sqlite3.Binary(blob),verified))
 db.execute("UPDATE arno_v3_archive_crosswalk SET byte_status='VERIFIED_AND_EMBEDDED_V5_ARCHIVE_VAULT' WHERE archive_name=? AND member_path=?",(ar,member))
pkg=proof.execute("SELECT path,sha256 FROM zip_inspection WHERE path LIKE '%ARNO_A_C_ALL12_EVIDENCE_INPUT.zip'").fetchone()
assert pkg and pkg[1]=="d0319135b633c5c0d949e705af4ad99f7a415bd2cd6357d9fbe101bebf3e27b1"
actual=ROOT/pkg[0]
assert filehash(actual)==pkg[1],"A/C input ZIP not physically verified"
proof.close()
records=db.execute("SELECT run_id,source_status,cohort,arm,input_zip_sha256,ingested_in_overlay FROM arno_v3_run_evidence").fetchall()
assert len(records)==33
corrected=0;versions=0
for run,kind,cohort,arm,oldzip,overlay in records:
 assets=dict(db.execute("SELECT role,zlib_blob FROM arno_v3_asset_bytes WHERE run_id=?",(run,)).fetchall())
 def raw(role):return zlib.decompress(assets[role])
 sr=json.loads(raw("SCANNER_RUN_RESULT"))
 sarif=json.loads(raw("CODEQL_AFTER_SARIF"))
 baseline=json.loads(raw("CODEQL_BEFORE_SARIF"))
 def version(doc):
  versions={x.get("tool",{}).get("driver",{}).get("semanticVersion") or x.get("tool",{}).get("driver",{}).get("version") for x in doc.get("runs",[])}
  assert len(versions)==1
  return versions.pop()
 v=version(sarif)
 assert v=="2.25.6" and version(baseline)==v,run
 if overlay:
  row=db.execute("SELECT scanner_version FROM arno_experiment_scans_overlay WHERE run_id=?",(run,)).fetchone()
  assert row and row[0] is None
  db.execute("UPDATE arno_experiment_scans_overlay SET scanner_version=? WHERE run_id=?",(v,run))
  db.execute("INSERT INTO arno_v5_correction_ledger VALUES(?,?,?,?,?,?,?)",(
   run,"scanner_version",None,v,digest(raw("CODEQL_AFTER_SARIF")),1,
   "Recovered from both original baseline and after SARIF"))
  versions+=1
 if cohort.startswith("OCT2026_AC"):
  sourcezip=sr["source_zip_sha256"];inputzip=sr["input_zip_sha256"]
  assert oldzip==sourcezip and inputzip==pkg[1],run
  db.execute("UPDATE arno_v3_run_evidence SET input_zip_sha256=?,source_zip_sha256=?,input_zip_verification_status=? WHERE run_id=?",(
   inputzip,sourcezip,"PHYSICALLY_VERIFIED_ACTUAL_AC_INPUT_ZIP_SHA256",run))
  db.execute("INSERT INTO arno_v5_correction_ledger VALUES(?,?,?,?,?,?,?)",(
   run,"input_zip_sha256",oldzip,inputzip,digest(raw("SCANNER_RUN_RESULT")),1,
   "Source ZIP hash mislabeled as input ZIP hash; actual input ZIP SHA checked against physical Wits ZIP; source hash preserved"))
  corrected+=1
 else:
  assert oldzip==sr.get("original_input_zip_sha256"),run
  db.execute("UPDATE arno_v3_run_evidence SET source_zip_sha256=?,input_zip_verification_status=? WHERE run_id=?",(
   oldzip,"SOURCE_ZIP_SHA_RECORDED_IN_VERIFIED_SCAN_RESULT",run))
 db.execute("INSERT INTO arno_v5_reproducibility VALUES(?,?,?,?,?,?,?)",(
  run,v,sr.get("suite") or "codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
  int("PROMPT" in assets),0,0,kind))
assert corrected==12 and versions==26
db.execute("UPDATE arno_v3_gap_ledger SET status='RESOLVED_V5_150_MEMBERS_BYTE_VERIFIED' WHERE gap_id='ARCHIVE_ONLY_150'")
for key,value in [
 ("parent_v3_sha256",PARENT_SHA),
 ("archive_proof_source_sha256",PROOF_SHA),
 ("AC_input_zip_sha256",pkg[1]),
 ("new_overlay_runs","26"),
 ("combined_v1_external_plus_overlay_runs","94"),
 ("remaining_gap_records","15"),
 ("scope","Scanner-only experiment; functionality and generator attestation not demonstrated"),
 ("v1_dependency","Original 42GB frozen v1 is external and read-only, needed for 68 prior study_runs")
]:
 db.execute("INSERT INTO arno_v5_release_info VALUES(?,?)",(key,value))
db.commit()
assert db.execute("PRAGMA quick_check").fetchone()[0]=="ok"
assert db.execute("SELECT COUNT(*) FROM arno_v5_archive_raw_patches").fetchone()[0]==150
assert db.execute("SELECT COUNT(*) FROM arno_v3_asset_bytes").fetchone()[0]==207
assert db.execute("SELECT COUNT(*) FROM arno_v5_correction_ledger").fetchone()[0]==38
assert db.execute("SELECT COUNT(*) FROM arno_v3_gap_ledger WHERE status='PENDING'").fetchone()[0]==15
assert db.execute("SELECT COUNT(*) FROM study_runs_overlay").fetchone()[0]==26
assert db.execute("SELECT COUNT(*) FROM arno_v5_reproducibility").fetchone()[0]==33
assert db.execute("SELECT COUNT(*) FROM arno_experiment_scans_overlay WHERE scanner_version IS NULL").fetchone()[0]==0
db.close()
os.replace(PART,FINAL)
report={"status":"PASS_WITH_DISCLOSED_LIMITATIONS","v5_path":str(FINAL),
"v5_sha256":filehash(FINAL),"bytes":FINAL.stat().st_size,"prior_runs_external":68,
"new_overlay_runs":26,"run_evidence":33,"embedded_replay_assets":207,
"embedded_recovered_archive_patches":150,"A_C_input_zip_physically_verified":True,
"A_C_corrected_hash_labels":12,"filled_scanner_version_rows":26,
"open_gap_records":15,"functional_tests_complete":False}
QA.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
