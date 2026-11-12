#!/usr/bin/env python3
"""Supersede mistaken earlier workbook in NEW reviewer SQLite; preserve historical master and V3."""
import sqlite3,shutil,hashlib,json,zipfile,datetime
from pathlib import Path
root=Path.home()/"research_artifacts"
src=root/"mcp_uploads/jobs/arno_d7_human_review_ingest_20261031_v1/result/ARNO_REVIEWER_WITH_D7_ASSISTED_ANNOTATIONS_20261031_V3.sqlite"
master=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
out=root/"mcp_uploads/jobs/arno_d7_corrected_workbook_v4_20261031/output"
out.mkdir(parents=True,exist_ok=False)
target=out/"ARNO_REVIEWER_WITH_CORRECTED_D7_ANNOTATIONS_V4_VERIFIED.sqlite"
oldsha="29628474c8663401a7c3c31b8be271248373303c4a8b66a482d8556ab5595e86"
newsha="e2370e44b64a051db061642e271e671310fba19969af24421291214fa339925e"
sidecarsha="b10f19f002f0447f6816d95aff9808e9cb53a6633750b560e7bc513682733e74"
bundle_sha="8504caa8c7ef48c1cddc5c8c869bbdf9f1c8b52698cebd2b566134ff2dfbbec2"
assert src.exists() and master.exists()
assert hashlib.sha256(src.read_bytes()).hexdigest()=="fb775f4c2dbd52d296304dbd78ef46f26dd835bc08e9593defc615a25c996309"
shutil.copy2(src,target)
con=sqlite3.connect(str(target))
con.execute("PRAGMA foreign_keys=ON")
con.execute("PRAGMA defer_foreign_keys=ON")
q=con.execute("SELECT batch_id,source_workbook_sha256,selected_verdicts,consensus_without_user_verdict,deferred_cases FROM human_review_batches").fetchall()
assert len(q)==1 and q[0][1:]==(oldsha,41,8,1),q
oldid=q[0][0]
newid="ARNO_D7_CORRECTED_HUMAN_SELECTED_50_20261031_V2"
# Update only source metadata and stable batch key; the 50 root/case IDs and label values are unchanged.
# Child batch IDs first because existing V3 does not declare FK constraints for these archival tables.
con.execute("UPDATE human_review_labels SET batch_id=? WHERE batch_id=?",(newid,oldid))
con.execute("UPDATE human_review_batches SET batch_id=?,source_workbook_sha256=?,review_mode=?,annotation_reason_source=? WHERE batch_id=?",
 (newid,newsha,"POST_HOC_AI_ASSISTED_HUMAN_SELECTED_NOT_INDEPENDENT_BLIND",
  "Corrected complete rationale, 227 evidence records and exact workbook bytes in local source sidecar ARNO_D7_CORRECTED_REVIEW_SIDECAR.sqlite sha256="+sidecarsha,oldid))
con.execute("""CREATE TABLE corrected_annotation_source_manifest(
  source_sha256 TEXT PRIMARY KEY,source_filename TEXT NOT NULL,revision_id TEXT NOT NULL,
  supersedes_sha256 TEXT NOT NULL,source_sidecar_sha256 TEXT NOT NULL,
  local_bundle_sha256 TEXT NOT NULL,verdict_values_changed INTEGER NOT NULL CHECK(verdict_values_changed=0),
  full_rationale_embedded_in_this_sqlite INTEGER NOT NULL CHECK(full_rationale_embedded_in_this_sqlite=0),
  corrected_full_source_available_in_sidecar INTEGER NOT NULL CHECK(corrected_full_source_available_in_sidecar=1),
  provenance_policy TEXT NOT NULL
)""")
con.execute("INSERT INTO corrected_annotation_source_manifest VALUES (?,?,?,?,?,?,?,?,?,?)",
 (newsha,"ARNO_D7_HUMAN_ANNOTATIONS_COMPLETE_50_CASES.xlsx",newid,oldsha,sidecarsha,bundle_sha,0,0,1,
 "41 post-hoc human-selected AI/evidence-assisted judgments; 8 consensus-only; 1 deferred; no independent blind second human rater"))
con.execute("""CREATE TABLE superseded_annotation_batches(
 prior_batch_id TEXT PRIMARY KEY,active_batch_id TEXT NOT NULL,
 reason TEXT NOT NULL,prior_workbook_sha256 TEXT NOT NULL,
 replacement_workbook_sha256 TEXT NOT NULL
)""")
con.execute("INSERT INTO superseded_annotation_batches VALUES (?,?,?,?,?)",(
 oldid,newid,"User corrected previously uploaded source; all 50 selected label values unchanged, textual attribution/evidence notes revised",oldsha,newsha))
con.execute("INSERT OR REPLACE INTO release_metadata (key,value) VALUES (?,?)",(
 "current_annotation_source_sha256",newsha))
con.execute("INSERT OR REPLACE INTO release_metadata (key,value) VALUES (?,?)",(
 "review_provenance","POST_HOC_HUMAN_SELECTED_WITH_AI_ASSISTANCE_NOT_BLIND_INTER_RATER"))
con.commit()
assert con.execute("PRAGMA quick_check").fetchone()[0]=="ok"
assert con.execute("PRAGMA foreign_key_check").fetchall()==[]
assert con.execute("SELECT COUNT(*) FROM human_review_labels").fetchone()[0]==50
assert con.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_ADJUDICATED'").fetchone()[0]==41
assert con.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='ALL_THREE_AGREE_NO_USER_VERDICT'").fetchone()[0]==8
assert con.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_DEFERRED'").fetchone()[0]==1
assert con.execute("SELECT COUNT(*) FROM human_review_labels WHERE human_selected_route=original_route AND verdict_status='USER_ADJUDICATED'").fetchone()[0]==41
con.close()
# Independent read-only source reference check of frozen labels, excluding N/A typographic difference.
raw=sqlite3.connect("file:"+str(master)+"?mode=ro",uri=True)
db=sqlite3.connect("file:"+str(target)+"?mode=ro",uri=True)
rows=db.execute("SELECT root_id,case_id,original_route,original_tier FROM human_review_labels").fetchall()
for root_id,case_id,route,tier in rows:
 reference=raw.execute("SELECT case_id,final_route,final_tier FROM arno_d7_final_roots_342 WHERE root_id=?",(root_id,)).fetchone()
 assert reference is not None and reference[0]==case_id and reference[1]==route
 assert str(reference[2]).replace("/","")==str(tier).replace("/",""),(root_id,tier,reference)
raw.close();db.close()
sha=hashlib.sha256(target.read_bytes()).hexdigest()
report={"status":"CORRECTED_SOURCE_SUPERSEDED_AND_VERIFIED","wits_master_edited":False,"prior_v3_edited":False,
 "new_v4_path":str(target),"new_v4_sha256":sha,"new_v4_bytes":target.stat().st_size,
 "source_file_sha256":newsha,"original_incorrect_workbook_sha256":oldsha,
 "separate_full_source_sidecar_sha256":sidecarsha,"mapping_matches_wits_master":50,
 "human_selected":41,"consensus_only":8,"deferred":1,"labels_changed_since_v3":0,
 "local_full_rationale_sidecar_required":True,"sqlite_quick_check":"ok"}
(out/"WITS_CORRECTED_IMPORT_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"READ_ME_FIRST.md").write_text(
"Corrected reviewer SQLite. References updated workbook hash. Prior Wits master and reviewer V3 are untouched. "
"The full corrected workbook, 50 source rows, 227 support records, and verbatim rationale live in matching downloadable "
"ARNO_D7_CORRECTED_REVIEW_SIDECAR.sqlite (hash given in corrected_annotation_source_manifest). "
"V4 stores reviewer join labels and the supersession manifest, not verbatim complete workbook content. "
"Do not claim independent blind human review. Static analysis findings remain scanner reports.\n")
with zipfile.ZipFile(out/"ARNO_WITS_CORRECTED_REVIEWER_V4.zip","w",zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for p in [target,out/"WITS_CORRECTED_IMPORT_REPORT.json",out/"READ_ME_FIRST.md"]:
  z.write(p,p.name)
print(json.dumps(report,indent=2))
