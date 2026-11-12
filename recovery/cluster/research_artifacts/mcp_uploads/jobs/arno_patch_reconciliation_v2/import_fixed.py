#!/usr/bin/env python3
"""Import verified deep experiments into NEW DB only; preserve all old rows."""
import sqlite3,hashlib,json,zipfile,re,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
W=R/"mcp_uploads/jobs/arno_patch_reconciliation_v2"
OUT=W/"output";DB=OUT/"ARNO_UNIFIED_EVIDENCE_WITH_DEEP_PATCHES_V2.sqlite"
assert (W/"PREFLIGHT_REPORT.json").exists() and (OUT/"SNAPSHOT_VERIFICATION.json").exists()
assert DB.exists()
M=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
E=R/"mcp_uploads/jobs/arno_20261030_rpl7_matched_evaluation"
S=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
U=R/"mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
A=R/"mcp_uploads/jobs/arno_ac6_v6_20261030/ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL_V6E.zip"
P=R/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/ready"
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return p.read_bytes()
def sf(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
db=sqlite3.connect(str(DB),timeout=240)
db.row_factory=sqlite3.Row
db.execute("PRAGMA foreign_keys=ON")
assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='study_deep_runs'").fetchone()
db.executescript("""
CREATE TABLE study_deep_runs(
 run_id TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 cohort_name TEXT NOT NULL,condition TEXT NOT NULL,
 source_kind TEXT NOT NULL,repo_tree_sha256 TEXT,
 original_input_sha256 TEXT,patch_sha256 TEXT NOT NULL,
 after_sarif_sha256 TEXT NOT NULL,baseline_sarif_sha256 TEXT NOT NULL,
 baseline_total INTEGER NOT NULL,after_total INTEGER NOT NULL,new_warnings INTEGER NOT NULL,
 strict_line_sensitive_count INTEGER, functional_status TEXT NOT NULL,
 agent_receipt_status TEXT NOT NULL,scan_status TEXT NOT NULL,
 result_json TEXT NOT NULL,source_archive TEXT NOT NULL,
 patch_source_status TEXT NOT NULL CHECK(patch_source_status='VERIFIED_EMBEDDED'));
CREATE TABLE study_deep_evidence(
 run_id TEXT NOT NULL,role TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
 raw_content BLOB NOT NULL,source_locator TEXT NOT NULL,
 PRIMARY KEY(run_id,role));
CREATE TABLE study_deep_baseline(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),
 baseline_total INTEGER NOT NULL,baseline_sarif_sha256 TEXT NOT NULL,
 raw_sarif BLOB NOT NULL,source_locator TEXT NOT NULL);
CREATE TABLE study_deep_input_packages(
 run_id TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 condition TEXT NOT NULL,input_sha256 TEXT NOT NULL,
 input_raw_zip BLOB NOT NULL,prompt_sha256 TEXT NOT NULL,
 original_prompt BLOB NOT NULL,repo_tree_sha256 TEXT NOT NULL,
 source_kind TEXT NOT NULL,original_path TEXT NOT NULL);
CREATE TABLE study_deep_pilot_inputs(
 pilot_condition TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 original_zip_sha256 TEXT NOT NULL,original_zip BLOB NOT NULL,
 prompt_sha256 TEXT NOT NULL,prompt BLOB NOT NULL,
 output_generation_status TEXT NOT NULL,
 reused_original_patch_sha256 TEXT);
CREATE TABLE study_deep_vault_patch_index(
 archive_name TEXT NOT NULL,member_path TEXT NOT NULL,
 claimed_member_sha256 TEXT NOT NULL,source_member_bytes INTEGER NOT NULL,
 case_id INTEGER,source_vault_object_key TEXT NOT NULL REFERENCES arno_archive_vault_objects(object_key),
 matched_in_previous_master INTEGER NOT NULL,
 matched_tables TEXT,member_verification_level TEXT NOT NULL,
 PRIMARY KEY(archive_name,member_path));
CREATE TABLE study_deep_integration_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
""")
db.execute("BEGIN IMMEDIATE")
manifest=json.loads((M/"MANIFEST.json").read_text())["runs"]
evals={r["run_id"]:r for r in json.loads((E/"EVALUATION.json").read_text())["runs"]}
assert len(manifest)==len(evals)==21
def evsave(run,role,payload,where):
 assert isinstance(payload,bytes)
 db.execute("INSERT INTO study_deep_evidence VALUES(?,?,?,?,?,?)",
            (run,role,sha(payload),len(payload),payload,where))
with zipfile.ZipFile(U) as patches:
 assert patches.testzip() is None and len(patches.namelist())==42
 for entry in manifest:
  run=entry["run_id"];cid=int(entry["case_id"]);cond=entry["condition"]
  er=evals[run];scan=S/("CASE_%05d"%cid)/run
  result_bytes=load(scan/"RESULT.json");result=json.loads(result_bytes)
  patch=patches.read("PATCH_"+run+".patch")
  receipt=patches.read("RECEIPT_"+run+".json")
  after=load(scan/"after.sarif")
  baseline=B/("CASE_%05d"%cid)/"baseline.sarif"
  origbase=load(baseline)
  assert sha(patch)==er["patch_sha256"]==result["patch_sha256"]
  assert sha(after)==er["scan_sarif_sha256"]==result["after_sarif_sha256"]
  assert sha(origbase)==result["baseline_sarif_sha256"]
  src=M/"run_zips"/(run+".zip")
  assert sf(src)==entry["sha256"]
  with zipfile.ZipFile(src) as inputz:
   prompt=inputz.read("PROMPT.md")
   assert sha(prompt)==entry["prompt_sha256"],("input prompt hash",run)
  if cond=="P1":
   old=db.execute("SELECT patch_blob,content_sha256 FROM arno_generated_patches WHERE run_id=?",(run,)).fetchone()
   assert old and sha(old["patch_blob"])==er["patch_sha256"]==old["content_sha256"],("old P1 different",run)
  else:
   assert not db.execute("SELECT 1 FROM study_runs WHERE run_id=?",(run,)).fetchone()
   db.execute("INSERT INTO study_deep_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
    run,cid,"RPL7_RETROSPECTIVE_ORACLE",cond,entry["source_kind"],entry["repo_tree_sha256"],
    entry["sha256"],sha(patch),sha(after),sha(origbase),
    result["before_total"],result["after_total"],result["new_conservative_line_agnostic"],
    result.get("new_strict_line_including"),result["functional_status"],
    result.get("receipt_generation_status","UNSPECIFIED"),result["status"],
    result_bytes.decode("utf-8"),str(U.relative_to(R)),"VERIFIED_EMBEDDED"))
  # All 21 runs get original prompt, returned patch and exact scanner evidence, including existing P1.
  db.execute("INSERT INTO study_deep_input_packages VALUES(?,?,?,?,?,?,?,?,?,?)",(
   run,cid,cond,entry["sha256"],load(src),sha(prompt),prompt,entry["repo_tree_sha256"],
   entry["source_kind"],str(src.relative_to(R))))
  for role,raw,source in (
    ("patch",patch,str(U.relative_to(R))+"::PATCH_"+run+".patch"),
    ("receipt",receipt,str(U.relative_to(R))+"::RECEIPT_"+run+".json"),
    ("after_sarif",after,str((scan/"after.sarif").relative_to(R))),
    ("scan_result",result_bytes,str((scan/"RESULT.json").relative_to(R)))):
   evsave(run,role,raw,source)
  if not db.execute("SELECT 1 FROM study_deep_baseline WHERE case_id=?",(cid,)).fetchone():
   db.execute("INSERT INTO study_deep_baseline VALUES(?,?,?,?,?)",(
     cid,result["before_total"],sha(origbase),origbase,str(baseline.relative_to(R))))
  else:
   b=db.execute("SELECT baseline_sarif_sha256,baseline_total FROM study_deep_baseline WHERE case_id=?",(cid,)).fetchone()
   assert b["baseline_sarif_sha256"]==sha(origbase) and b["baseline_total"]==result["before_total"]
# A/C pilot: distinct non-randomized intervention and source protocol. Never relabel as historical OWP.
with zipfile.ZipFile(A) as z:
 assert z.testzip() is None
 for cs in ["03429","03581","08152","12344","31207","32759"]:
  cid=int(cs)
  for cond in ("MECHANISM","PROSPECTIVE_BUILD"):
   prefix="results_v6c/CASE_"+cs+"/"+cond+"/"
   result_raw=z.read(prefix+"RESULT.json");result=json.loads(result_raw)
   run=result["run_id"];patch=z.read(prefix+"PATCH.patch")
   sarif=z.read(prefix+"after.sarif");receipt=z.read(prefix+"RECEIPT.json")
   assert run=="PILOT"+cs+"_"+cond+"_R1"
   assert sha(patch)==result["patch_sha256"] and sha(sarif)==result["after_sarif_sha256"]
   assert sha(receipt)==result["receipt_sha256"]
   base=db.execute("SELECT baseline_sarif_sha256,baseline_total FROM study_deep_baseline WHERE case_id=?",(cid,)).fetchone()
   assert base and result["baseline_sarif_sha256"]==base["baseline_sarif_sha256"],("base mismatch",run)
   assert result["baseline_total"]==base["baseline_total"],("baseline count",run)
   db.execute("INSERT INTO study_deep_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
    run,cid,"AC6_EXPLORATORY_NONRANDOMIZED",cond,result["source_kind"],
    result["repo_tree_sha256"],result.get("input_zip_sha256"),
    sha(patch),sha(sarif),result["baseline_sarif_sha256"],
    result["baseline_total"],result["after_total"],result["new_conservative_line_agnostic"],
    result.get("new_strict_line_including"),result["functional_status"],
    result["agent_generation_status"],result["status"],
    result_raw.decode("utf-8"),str(A.relative_to(R)),"VERIFIED_EMBEDDED"))
   for name,raw in (("patch",patch),("receipt",receipt),("after_sarif",sarif),("scan_result",result_raw)):
    arname={"patch":"PATCH.patch","receipt":"RECEIPT.json","after_sarif":"after.sarif","scan_result":"RESULT.json"}[name]
    evsave(run,name,raw,str(A.relative_to(R))+"::"+prefix+arname)
   # Preserve structured pre-implementation risk anticipation if actually delivered.
   opt=prefix+"RISKS.json"
   if opt in z.namelist():evsave(run,"prospective_risks",z.read(opt),str(A.relative_to(R))+"::"+opt)
# Case 22223 A/B/C uploads are inputs, not proof that B independently generated/scanned a patch.
pilot_paths={"A_MECHANISM":"ARNO_22223_A_MECHANISM_UPLOAD.zip",
             "B_BLIND_REVIEW":"ARNO_22223_B_BLIND_REVIEW_UPLOAD.zip",
             "C_PROSPECTIVE_RISKS":"ARNO_22223_C_PROSPECTIVE_RISKS_UPLOAD.zip"}
for label,filename in pilot_paths.items():
 path=P/filename
 with zipfile.ZipFile(path) as z:
  prompt=z.read("PROMPT.md")
  old_patch=z.read("P1_PATCH.patch") if "P1_PATCH.patch" in z.namelist() else None
 db.execute("INSERT INTO study_deep_pilot_inputs VALUES(?,?,?,?,?,?,?,?)",(
  label,22223,sf(path),load(path),sha(prompt),prompt,"INPUT_ONLY_NO_INDEPENDENT_RETURNED_B_SCAN" if label=="B_BLIND_REVIEW" else "PREPARED_INPUT_NOT_FRESH_RUN",
  sha(old_patch) if old_patch else None))
# Index *all* historical vault patch files to their embedded original archive object.
for row in db.execute("""SELECT archive_name,member_path,sha256,original_bytes,case_id,indexed_in_master,matched_master_tables
FROM arno_archive_vault_members WHERE role='PATCH'""").fetchall():
 obj="archive:"+row["archive_name"]
 assert db.execute("SELECT 1 FROM arno_archive_vault_objects WHERE object_key=?",(obj,)).fetchone(),obj
 m=re.search(r"CASE_(\d+)",row["member_path"],re.I)
 case=int(m.group(1)) if m else None
 if case is not None and not db.execute("SELECT 1 FROM cases WHERE id=?",(case,)).fetchone():case=None
 db.execute("INSERT INTO study_deep_vault_patch_index VALUES(?,?,?,?,?,?,?,?,?)",(
  row["archive_name"],row["member_path"],row["sha256"],row["original_bytes"],case,
  obj,row["indexed_in_master"],row["matched_master_tables"],
  "SOURCE_ARCHIVE_EMBEDDED_MANIFEST_HASH_CLAIM_NOT_INDEPENDENTLY_EXTRACTED"))
m={
"original_legacy_run_count":"68","new_registered_run_count":"26",
"rpl7_21_input_packages_and_full_outputs":"21","new_rpl7_p2_p3_runs":"14",
"ac6_pilot_scanned_runs":"12","separate_22223_a_b_c_prepared_inputs":"3",
"archive_patch_members":"255","archive_only_patch_members":"150",
"historical_labels_unchanged":"YES","public_distribution":"RESTRICTED_NOT_CLEARED",
"functional_correctness":"NOT_VERIFIED_FOR_DEEP_EXPERIMENTS",
"p2_p3_oracle_hindsight_warning":"RETROSPECTIVE_ORACLE_NOT_DEPLOYABLE",
"pilot_b_status":"INPUT_ONLY_NOT_SCANNED",
"ac_labels":"MECHANISM_PROSPECTIVE_BUILD_NOT_EQUIVALENT_TO_HISTORICAL_P1_P2_P3"}
db.executemany("INSERT INTO study_deep_integration_metadata VALUES(?,?)",m.items())
db.executescript("""
CREATE INDEX study_deep_runs_case ON study_deep_runs(case_id);
CREATE INDEX study_deep_evidence_run ON study_deep_evidence(run_id);
CREATE INDEX study_deep_archive_patch_case ON study_deep_vault_patch_index(case_id);
CREATE VIEW study_all_experimental_runs AS
SELECT run_id,case_id,experimental_family AS experiment_family,treatment AS condition,
patch_sha256,after_sarif_sha256,before_count,
after_count,number_new AS new_count,functional_status,
'LEGACY_20261031' AS registration_source
FROM study_runs
UNION ALL
SELECT run_id,case_id,cohort_name,condition,patch_sha256,after_sarif_sha256,
baseline_total,after_total,new_warnings,functional_status,
'DEEP_PATCH_INTEGRATION' FROM study_deep_runs;
""")
assert db.execute("SELECT COUNT(*) FROM study_deep_runs").fetchone()[0]==26
assert db.execute("SELECT COUNT(*) FROM study_deep_input_packages").fetchone()[0]==21
assert db.execute("SELECT COUNT(*) FROM study_deep_baseline").fetchone()[0]==7
assert db.execute("SELECT COUNT(*) FROM study_deep_pilot_inputs").fetchone()[0]==3
assert db.execute("SELECT COUNT(*) FROM study_deep_vault_patch_index").fetchone()[0]==255
assert db.execute("SELECT COUNT(*) FROM study_all_experimental_runs").fetchone()[0]==94
assert db.execute("SELECT COUNT(*) FROM study_deep_evidence WHERE role='patch'").fetchone()[0]==33
assert db.execute("SELECT COUNT(*) FROM study_deep_evidence WHERE role='after_sarif'").fetchone()[0]==33
for t in ["study_deep_runs","study_deep_input_packages","study_deep_baseline","study_deep_pilot_inputs",
          "study_deep_vault_patch_index"]:
 assert not db.execute('PRAGMA foreign_key_check("'+t+'")').fetchall()
db.commit();db.close()
print(json.dumps({"status":"DEEP_PATCHES_INTEGRATED","old_runs":68,"new_runs":26,
"total_runs":94,"rpl7_source_input_zips":21,"patches_and_scans_deep_evidence":33,
"vault_patch_members_indexed":255,"B_prepared_only":True},indent=2),flush=True)
