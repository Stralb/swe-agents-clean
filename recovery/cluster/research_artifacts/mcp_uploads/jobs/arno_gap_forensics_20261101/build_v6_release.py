#!/usr/bin/env python3
"""Non-destructive V6 join of 18 original packet prompts and 22223 three scans into V5."""
import sqlite3,hashlib,json,zlib,shutil,os
from collections import Counter
from pathlib import Path
R=Path.home()/"research_artifacts";J=R/"mcp_uploads/jobs"
old=J/"arno_peer_review_recovery_20261101/final_v5/ARNO_REPLAY_EVIDENCE_v5_ARCHIVES_AND_CORRECTIONS.sqlite"
supp=J/"arno_gap_forensics_20261101/addendum_v1/RECOVERED_A_C_INPUT_PROMPTS_AND_22223.sqlite"
out=J/"arno_gap_forensics_20261101/release_v6";out.mkdir(parents=True,exist_ok=True)
dest=out/"ARNO_REPLAY_EVIDENCE_V6_WITH_RECOVERED_PROMPTS_22223.sqlite"
part=out/"ARNO_REPLAY_EVIDENCE_V6_WITH_RECOVERED_PROMPTS_22223.sqlite.partial"
report=out/"RELEASE_V6_VERIFICATION.json"
assert not dest.exists() and not part.exists() and not report.exists()
def H(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(4*1024*1024),b""):h.update(x)
 return h.hexdigest()
assert H(old)=="ebc5450f9a443e5fdff3bcd963ce997a5f97501db6a215bae00af8adf446edee"
assert H(supp)=="111b1578d3ce615a0cdbb6ce8520cdf21bb36408f8dcedf805b8413890657262"
shutil.copyfile(old,part)
db=sqlite3.connect(str(part),timeout=60)
db.execute("ATTACH DATABASE ? AS proof",("file:"+str(supp)+"?mode=ro",))
db.executescript("""
CREATE TABLE arno_v6_initial_packet AS SELECT * FROM proof.initial_packets WHERE 0;
CREATE UNIQUE INDEX ix_v6_packet ON arno_v6_initial_packet(case_id,arm);
CREATE TABLE arno_v6_22223_scanned_run AS SELECT * FROM proof.recovered_22223 WHERE 0;
CREATE UNIQUE INDEX ix_v6_22223 ON arno_v6_22223_scanned_run(arm);
CREATE TABLE arno_v6_22223_assets AS SELECT * FROM proof.recovered_22223_assets WHERE 0;
CREATE UNIQUE INDEX ix_v6_22223_assets ON arno_v6_22223_assets(arm,role);
CREATE TABLE arno_v6_recovery_provenance(key TEXT PRIMARY KEY,value TEXT NOT NULL);
""")
db.execute("INSERT INTO arno_v6_initial_packet SELECT * FROM proof.initial_packets")
db.execute("INSERT INTO arno_v6_22223_scanned_run SELECT * FROM proof.recovered_22223")
db.execute("INSERT INTO arno_v6_22223_assets SELECT * FROM proof.recovered_22223_assets")
# Compare the three independently generated scanner results against frozen source baseline.
p1=db.execute("""SELECT run_id FROM arno_v3_run_evidence
 WHERE case_id=22223 AND arm='P1'""").fetchone()
assert p1
base_blob=db.execute("""SELECT zlib_blob FROM arno_v3_asset_bytes
 WHERE run_id=? AND role='CODEQL_BEFORE_SARIF'""",(p1[0],)).fetchone()[0]
def counter(doc):
 c=Counter()
 for run in doc.get("runs",[]):
  for v in run.get("results",[]):
   loc=v.get("locations") or []
   path=(loc[0].get("physicalLocation",{}).get("artifactLocation",{}).get("uri","") if loc else "")
   msg=v.get("message") or {}
   c[(v.get("ruleId") or "",path,msg.get("text") or msg.get("markdown") or "")]+=1
 return c
base=counter(json.loads(zlib.decompress(base_blob)))
assert sum(base.values())==41,("baseline",sum(base.values()))
warning_recompute={}
for arm in "ABC":
 aft=db.execute("""SELECT data_zlib FROM arno_v6_22223_assets WHERE arm=? AND role='AFTER_SARIF'""",(arm,)).fetchone()[0]
 after=counter(json.loads(zlib.decompress(aft)))
 newly=sum((after-base).values())
 row=db.execute("SELECT new_warnings,after_results FROM arno_v6_22223_scanned_run WHERE arm=?",(arm,)).fetchone()
 warning_recompute[arm]={"independently_recomputed_new":newly,"reported_new":row[0],
 "total_after":sum(after.values())}
 assert newly==row[0]==0,(arm,newly,row)
 assert sum(after.values())==row[1]==41
for arm in "ABC":
 db.execute("UPDATE arno_v3_gap_ledger SET status=? WHERE gap_id=?",(
  "RESOLVED_V6_RETURNED_PATCH_RECEIPT_SCAN_HASHES_VERIFIED_FUNCTIONAL_NOT_TESTED","22223_"+arm))
for case in ("03429","03581","08152","12344","31207","32759"):
 for arm,status in (("MECHANISM","PROMPT_PACKET_VERIFIED_AGENT_RUNTIME_CONTEXT_UNATTESTED"),
                    ("PROSPECTIVE_BUILD","STAGE1_PROMPT_VERIFIED_STAGE2_RUNTIME_CONTEXT_UNATTESTED")):
  db.execute("UPDATE arno_v3_gap_ledger SET status=? WHERE gap_id=?",(
   status,"AC_PROMPT_PILOT"+case+"_"+arm+"_R1"))
for key,value in [
 ("parent_v5_sha256",H(old)),
 ("source_recovery_addendum_sha256",H(supp)),
 ("p1_p2_p3_and_ac_normalized_run_count","94"),
 ("additional_case22223_scanned_pilots","3"),
 ("total_distinct_experiment_records_in_v6","97 (94 original+overlay; 3 separately indexed case22223)"),
 ("scanner_scope","CODEQL only; no independent task-functional acceptance"),
 ("historical_original_o_patches_for_08461_15151","Unrecovered; recent GPT6 O reruns are not historical originals")
]:db.execute("INSERT INTO arno_v6_recovery_provenance VALUES(?,?)",(key,value))
db.commit()
assert db.execute("PRAGMA main.quick_check").fetchone()[0]=="ok"
assert db.execute("SELECT COUNT(*) FROM arno_v6_initial_packet").fetchone()[0]==18
assert db.execute("SELECT COUNT(*) FROM arno_v6_22223_scanned_run").fetchone()[0]==3
assert db.execute("SELECT COUNT(*) FROM arno_v3_gap_ledger WHERE status='PENDING'").fetchone()[0]==0
assert db.execute("SELECT COUNT(*) FROM arno_v3_gap_ledger WHERE status LIKE '%UNATTESTED'").fetchone()[0]==12
db.execute("DETACH DATABASE proof");db.close()
os.replace(part,dest)
result={"status":"PASS_WITH_PROVENANCE_LIMITATIONS","path":str(dest),"sha256":H(dest),"bytes":dest.stat().st_size,
 "recovered_packet_prompts":18,"recovered_verified_scanned_pilots":3,
 "normalized_run_count_v1_plus_v5_overlay":94,"separate_case22223_run_count":3,
 "new_warnings_22223":warning_recompute,
 "ac_generation_chat_attested":False,
 "ac_C_stage2_prompt_attested":False,
 "case22223_functional_validated":False}
report.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2),flush=True)
