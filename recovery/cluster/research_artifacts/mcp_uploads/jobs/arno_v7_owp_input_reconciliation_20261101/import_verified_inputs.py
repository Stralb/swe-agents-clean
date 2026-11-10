#!/usr/bin/env python3
"""Non-destructive V7 O/W/P original INPUT artifact import, strictly not patches.
The exact uploaded bytes are verified against existing frozen Wits input ZIPs.
Only makes a new release. The V6 database and source ZIPs are read-only.
"""
from pathlib import Path
import hashlib,json,os,sqlite3,shutil,zipfile
ROOT=Path.home()/"research_artifacts"
SRC=ROOT/"mcp_uploads/jobs/arno_gap_forensics_20261101/release_v6/ARNO_REPLAY_EVIDENCE_V6_WITH_RECOVERED_PROMPTS_22223.sqlite"
DESTDIR=ROOT/"mcp_uploads/jobs/arno_v7_owp_input_reconciliation_20261101/output"
DESTDIR.mkdir(parents=True,exist_ok=True)
DEST=DESTDIR/"ARNO_REPLAY_EVIDENCE_V7_WITH_VERIFIED_OWP_INPUTS.sqlite"
PART=DESTDIR/"ARNO_REPLAY_EVIDENCE_V7_WITH_VERIFIED_OWP_INPUTS.sqlite.partial"
QA=DESTDIR/"ARNO_V7_OWP_INPUT_IMPORT_QA.json"
MANIFEST={
 "08461":{"sha256":"cf604dce142adf1ddeda24d54f17944e6bdb3969d8a3e0b70febc0599e92d5a5","size":5724653,"repo_files":329},
 "15151":{"sha256":"25317a7d85f2208b372f69c746de2b6bb08f616b8c552a4b360fbd0b19af5270","size":53182961,"repo_files":3488},
}
V6_SHA="8767ab699b9bc23648402c6de80615e00436b0b56c4cb8ba670de9972d8e0fca"
if any(x.exists() for x in (DEST,PART,QA)):raise FileExistsError("Target already exists; refusing to overwrite")
def H(b):return hashlib.sha256(b).hexdigest()
def filehash(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
if filehash(SRC)!=V6_SHA:raise RuntimeError("Frozen V6 SHA mismatch; refusing to import")
verified=[]
for case,expect in MANIFEST.items():
 f=ROOT/"prevention_pilot_phase2/owp14_allcases_packets_job71014"/("CASE_"+case+"_O.zip")
 raw=f.read_bytes()
 assert len(raw)==expect["size"] and H(raw)==expect["sha256"], "Wits input ZIP differs from user-uploaded bytes: "+case
 with zipfile.ZipFile(f) as z:
  assert z.testzip() is None
  names=set(z.namelist())
  assert "ISSUE.md" in names and "RUN_INSTRUCTIONS.md" in names
  nrepo=sum(1 for n in names if n.startswith("REPO/") and not n.endswith("/"))
  assert nrepo==expect["repo_files"],(case,nrepo)
  # These are original task packets. Do not treat any included source .patch as a generated artifact.
  assert not any(n.endswith(".patch") and not n.startswith("REPO/") for n in names)
  issue_sha=H(z.read("ISSUE.md"))
  instructions_sha=H(z.read("RUN_INSTRUCTIONS.md"))
 verified.append({"case_id":int(case),"zip_path":str(f.relative_to(ROOT)), "zip_sha256":H(raw),
  "zip_bytes":len(raw),"repo_files":nrepo,"issue_sha256":issue_sha,
  "instructions_sha256":instructions_sha,"data":raw})
print("PRECHECK_VERIFIED_UPLOADED_ZIP_BYTES",json.dumps([{k:v for k,v in r.items() if k!="data"} for r in verified]),flush=True)
shutil.copyfile(SRC,PART)
db=sqlite3.connect(str(PART))
try:
 db.execute("""CREATE TABLE arno_v7_owp_original_input_archives(
   case_id INTEGER NOT NULL,
   arm TEXT NOT NULL CHECK(arm='O'),
   provided_filename TEXT NOT NULL,
   archived_cluster_path TEXT NOT NULL,
   archive_sha256 TEXT NOT NULL,
   archive_bytes INTEGER NOT NULL,
   repo_file_count INTEGER NOT NULL,
   issue_sha256 TEXT NOT NULL,
   run_instructions_sha256 TEXT NOT NULL,
   archive_blob BLOB NOT NULL,
   upload_to_archive_sha256_verified INTEGER NOT NULL,
   is_generated_patch INTEGER NOT NULL,
   historic_o_patch_proven INTEGER NOT NULL,
   distinction TEXT NOT NULL,
   PRIMARY KEY(case_id,arm)
 )""")
 db.execute("CREATE TABLE arno_v7_import_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
 for r in verified:
  db.execute("INSERT INTO arno_v7_owp_original_input_archives VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
    r["case_id"],"O","CASE_"+str(r["case_id"]).zfill(5)+"_O.zip",
    r["zip_path"],r["zip_sha256"],r["zip_bytes"],r["repo_files"],
    r["issue_sha256"],r["instructions_sha256"],sqlite3.Binary(r["data"]),1,0,0,
    "ORIGINAL_FROZEN_TASK_INPUT_ONLY; NOT AN AGENT OUTPUT; historic O patch still unverified"))
 for key,value in [
  ("parent_v6_sha256",V6_SHA),
  ("imported_role","ORIGINAL_TASK_INPUT_ZIP_NOT_PATCH"),
  ("original_historical_O_patches_for_08461_and_15151","UNVERIFIED_NOT_RESOLVED"),
  ("manuscript_denominator_change","NONE"),
  ("source_bytes_authentication","uploaded ZIP SHA256 matched physically existing Wits packet bytes"),
  ("source_v6_preserved","YES")
 ]:db.execute("INSERT INTO arno_v7_import_metadata VALUES(?,?)",(key,value))
 db.commit()
 for r in verified:
  row=db.execute("SELECT archive_blob,archive_sha256,is_generated_patch,historic_o_patch_proven FROM arno_v7_owp_original_input_archives WHERE case_id=?",(r["case_id"],)).fetchone()
  assert H(row[0])==row[1]==r["zip_sha256"] and row[2:]==(0,0)
 assert db.execute("PRAGMA main.quick_check").fetchone()[0]=="ok"
 assert db.execute("SELECT COUNT(*) FROM arno_v7_owp_original_input_archives").fetchone()[0]==2
 assert db.execute("SELECT COUNT(*) FROM study_runs_overlay").fetchone()[0]==26
 assert db.execute("SELECT COUNT(*) FROM arno_v6_22223_scanned_run").fetchone()[0]==3
 assert db.execute("SELECT COUNT(*) FROM arno_v5_archive_raw_patches").fetchone()[0]==150
 assert db.execute("SELECT COUNT(*) FROM arno_v3_asset_bytes").fetchone()[0]==207
finally:db.close()
os.replace(PART,DEST)
result={"status":"PASS_INPUTS_IMPORTED_NOT_PATCHES",
 "parent_v6_sha256":V6_SHA,"output_path":str(DEST),
 "output_sha256":filehash(DEST),"output_bytes":DEST.stat().st_size,
 "imported_original_input_archives":[{k:v for k,v in x.items() if k!="data"} for x in verified],
 "input_archives_embedded":2,
 "historic_O_patches_recovered":0,
 "original_O_scanned_patch_cohort_size_unchanged":12,
 "v6_plus_v7_evidence_state_preserved":True}
QA.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2),flush=True)
