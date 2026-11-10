#!/usr/bin/env python3
"""Link all run/patch/SARIF/scan evidence and corrected human audit, preserving raw bytes in legacy tables."""
import sqlite3,json,hashlib
from pathlib import Path
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
DB=O/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
V4=R/"mcp_uploads/jobs/arno_d7_corrected_workbook_v4_20261031/output/ARNO_REVIEWER_WITH_CORRECTED_D7_ANNOTATIONS_V4_RELEASED.sqlite"
assert (O/"CORE_COUNTS.json").exists() and V4.exists()
db=sqlite3.connect(str(DB),timeout=180)
db.row_factory=sqlite3.Row
db.execute("PRAGMA foreign_keys=ON")
v4=sqlite3.connect("file:"+str(V4)+"?mode=ro",uri=True);v4.row_factory=sqlite3.Row
assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='study_runs'").fetchone()
db.executescript("""
CREATE TABLE study_runs(
 run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER REFERENCES cases(id),
 experimental_family TEXT NOT NULL,treatment TEXT,run_status TEXT NOT NULL,
 source_snapshot_type TEXT,
 patch_id TEXT,patch_sha256 TEXT,patch_embedded INTEGER NOT NULL CHECK(patch_embedded IN(0,1)),
 scan_id TEXT,raw_scan_embedded INTEGER NOT NULL CHECK(raw_scan_embedded IN(0,1)),
 scan_execution_verified INTEGER,
 before_count INTEGER,after_count INTEGER,number_new INTEGER,number_new_target INTEGER,
 before_sarif_sha256 TEXT,after_sarif_sha256 TEXT,
 historical_revision_equivalence TEXT,
 functional_status TEXT,patch_provenance_status TEXT,
 raw_patch_source_table TEXT,raw_scan_source_table TEXT,metrics_source_table TEXT);
CREATE TABLE study_artifacts(
 artifact_id TEXT PRIMARY KEY,
 case_id INTEGER REFERENCES cases(id),run_id TEXT,
 role TEXT NOT NULL,source_table TEXT NOT NULL,source_locator TEXT NOT NULL,
 sha256 TEXT,storage_status TEXT NOT NULL,original_bytes INTEGER);
CREATE TABLE study_human_reviews(
 review_id TEXT PRIMARY KEY,root_id TEXT NOT NULL REFERENCES study_roots(root_id),
 case_id INTEGER NOT NULL REFERENCES study_cases(case_id),
 status TEXT NOT NULL,prior_route TEXT,prior_tier TEXT,
 selected_route TEXT,selected_tier TEXT,
 review_run_a TEXT,review_run_b TEXT,comparison_status TEXT,
 review_method TEXT NOT NULL,source_workbook_sha256 TEXT NOT NULL);
CREATE TABLE study_limitations(
 issue_id TEXT PRIMARY KEY,severity TEXT NOT NULL,description TEXT NOT NULL);
CREATE TABLE study_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
""")
db.execute("BEGIN IMMEDIATE")
for e in db.execute("SELECT run_id,case_id,experiment_family,treatment,status FROM arno_experiment_runs").fetchall():
 rid=e["run_id"];case=e["case_id"];fam=e["experiment_family"]
 p=db.execute("SELECT patch_id,content_sha256,patch_blob,authenticity_status FROM arno_generated_patches WHERE run_id=?",(rid,)).fetchone()
 s=db.execute("SELECT scan_id,raw_result_blob,execution_verified FROM arno_experiment_scans WHERE run_id=?",(rid,)).fetchone()
 assert s is not None,("MISSING_SCAN",rid)
 m=db.execute("SELECT * FROM arno_chat_codeql_metrics WHERE run_id=?",(rid,)).fetchone()
 h=base=None
 if fam=="RQ3_OWP14_ARCHIVED_SCAN_ARM":
  h=db.execute("SELECT * FROM arno_rq3_owp14_run_scans WHERE case_id=? AND arm=?",(case,e["treatment"])).fetchone()
  base=db.execute("SELECT * FROM arno_owp14_exact_scan_baseline_links_20261029 WHERE case_id=? AND arm=?",(case,e["treatment"])).fetchone()
  assert h is not None and base is not None,("MISSING_HISTORICAL_SCAN_BASELINE",rid)
  assert m is None,("MIXED_METRICS",rid)
 else:
  assert m is not None,("MISSING_RECENT_METRICS",rid)
 db.execute("""INSERT INTO study_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
  rid,case,fam,e["treatment"],e["status"],
  h["source_snapshot_type"] if h else m["source_kind"],
  p["patch_id"] if p else None,p["content_sha256"] if p else None,
  int(bool(p and p["patch_blob"] is not None)),
  s["scan_id"],int(bool(s["raw_result_blob"] is not None)),s["execution_verified"],
  m["baseline_total"] if m else None,m["after_total"] if m else None,
  m["new_vs_baseline"] if m else h["new_strong_count"],
  m["historical_p1_new"] if m else h["target_new_strong"],
  base["baseline_sarif_sha256"] if base else None,
  m["sarif_sha256"] if m else h["result_sha256"],
  base["historical_pr_revision_equivalence"] if base else "NOT_ATTESTED",
  m["functional_status"] if m else h["functional_status"],
  p["authenticity_status"] if p else "NO_PATCH_BASELINE",
  "arno_generated_patches" if p else None,"arno_experiment_scans",
  "arno_chat_codeql_metrics" if m else "arno_rq3_owp14_run_scans"))
# Raw source objects are indexed, not removed or replaced; source table and SHA remain queryable.
for r in db.execute("""SELECT p.patch_id,p.run_id,e.case_id,p.content_sha256,length(p.patch_blob) bytes
FROM arno_generated_patches p JOIN arno_experiment_runs e ON p.run_id=e.run_id""").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "patch:"+r["patch_id"],r["case_id"],r["run_id"],"PATCH",
 "arno_generated_patches",r["patch_id"],r["content_sha256"],"EMBEDDED_BYTES",r["bytes"]))
for r in db.execute("""SELECT s.scan_id,s.run_id,e.case_id,length(s.raw_result_blob) bytes
FROM arno_experiment_scans s JOIN arno_experiment_runs e ON s.run_id=e.run_id""").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "scan:"+r["scan_id"],r["case_id"],r["run_id"],"SCAN",
 "arno_experiment_scans",r["scan_id"],None,"EMBEDDED_BYTES",r["bytes"]))
for r in db.execute("""SELECT artifact_id,run_id,case_id,role,sha256,original_bytes,content_zlib
FROM arno_chat_evidence_objects""").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "evidence:"+r["artifact_id"],r["case_id"],r["run_id"],r["role"],
 "arno_chat_evidence_objects",r["artifact_id"],r["sha256"],
 "ZLIB_EMBEDDED" if r["content_zlib"] is not None else "EXTERNAL_ONLY",r["original_bytes"]))
for r in db.execute("SELECT case_id,arm,patch_sha256,original_patch_bytes FROM arno_rq3_owp14_verified_patch_bytes").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "historical_patch:%s:%s"%(r["case_id"],r["arm"]),r["case_id"],None,
 "HISTORICAL_PATCH","arno_rq3_owp14_verified_patch_bytes",
 str(r["case_id"])+":"+r["arm"],r["patch_sha256"],"ZLIB_EMBEDDED",r["original_patch_bytes"]))
for r in db.execute("SELECT case_id,arm,result_sha256,length(original_result_zlib) bytes FROM arno_rq3_owp14_run_scans").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "historical_scan:%s:%s"%(r["case_id"],r["arm"]),r["case_id"],None,
 "HISTORICAL_SCAN","arno_rq3_owp14_run_scans",
 str(r["case_id"])+":"+r["arm"],r["result_sha256"],"ZLIB_EMBEDDED",r["bytes"]))
for r in db.execute("SELECT case_id,result_sha256,length(result_zlib) bytes FROM arno_rq3_codeql_screen65_original").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "screen_scan:%s"%r["case_id"],r["case_id"],None,
 "SCREENING_SCANNER_RESULT","arno_rq3_codeql_screen65_original",
 str(r["case_id"]),r["result_sha256"],"ZLIB_EMBEDDED",r["bytes"]))
for r in db.execute("SELECT patch_key,case_id,patch_sha256,original_byte_count FROM arno_recovered_agent_patch_bytes").fetchall():
 db.execute("INSERT INTO study_artifacts VALUES(?,?,?,?,?,?,?,?,?)",(
 "recovered_patch:"+r["patch_key"],r["case_id"],None,
 "RECOVERED_PATCH","arno_recovered_agent_patch_bytes",
 r["patch_key"],r["patch_sha256"],"ZLIB_EMBEDDED",r["original_byte_count"]))
workbook_sha=v4.execute("SELECT source_workbook_sha256 FROM human_review_batches").fetchone()[0]
for r in v4.execute("SELECT * FROM human_review_labels"):
 db.execute("INSERT INTO study_human_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 r["review_id"],r["root_id"],r["case_id"],r["verdict_status"],
 r["original_route"],r["original_tier"],r["human_selected_route"],r["human_selected_tier"],
 r["run_a_label"],r["run_b_label"],r["comparison_to_original"],
 "ONE_HUMAN_POST_HOC_AI_ASSISTED_NOT_INDEPENDENT_BLIND",workbook_sha))
for r in v4.execute("SELECT issue_id,severity,description FROM scientific_limitations"):
 db.execute("INSERT INTO study_limitations VALUES(?,?,?)",tuple(r))
meta={
 "status":"RESTRICTED_FULL_EVIDENCE_DATABASE_NOT_PUBLIC_CLEARED",
 "original_master_unchanged":"YES",
 "original_tables_and_raw_bytes_preserved":"YES",
 "normalized_study_cases":"192",
 "normalized_canonical_findings":"842",
 "mapped_findings":"781","not_isolated_findings":"61",
 "normalized_producing_changes":"455",
 "root_decisions":"342","recorded_experiment_runs":"68",
 "human_review":"41_HUMAN_SELECTED_POSTHOC_8_CONSENSUS_1_DEFERRED",
 "single_human_no_independent_inter_rater":"YES",
 "corrected_workbook_sha256":workbook_sha,
 "historical_complete_owp_triples":"12",
 "nonblind_new_O_reruns":"2_NOT_HISTORICAL",
 "private_raw_evidence_license_check":"REQUIRED"
}
db.executemany("INSERT INTO study_metadata VALUES(?,?)",meta.items())
db.executescript("""
CREATE INDEX study_runs_case_idx ON study_runs(case_id);
CREATE INDEX study_artifacts_case_idx ON study_artifacts(case_id);
CREATE INDEX study_artifacts_run_idx ON study_artifacts(run_id);
CREATE VIEW study_paper_runs AS
SELECT run_id,case_id,experimental_family,treatment,run_status,
patch_id,patch_sha256,patch_embedded,scan_id,raw_scan_embedded,
before_count,after_count,number_new,number_new_target,
before_sarif_sha256,after_sarif_sha256,historical_revision_equivalence,functional_status
FROM study_runs;
CREATE VIEW study_paper_human_reviews AS
SELECT review_id,root_id,case_id,status,selected_route,selected_tier,
prior_route,prior_tier,review_method
FROM study_human_reviews;
""")
def n(q):return db.execute(q).fetchone()[0]
actual={t:n("SELECT COUNT(*) FROM "+t) for t in
 ["study_runs","study_artifacts","study_human_reviews","study_limitations"]}
assert actual=={"study_runs":68,"study_artifacts":633,"study_human_reviews":50,"study_limitations":12},actual
assert n("SELECT SUM(patch_embedded) FROM study_runs")==61
assert n("SELECT SUM(raw_scan_embedded) FROM study_runs")==68
assert n("SELECT COUNT(*) FROM study_human_reviews WHERE status='USER_ADJUDICATED'")==41
assert n("SELECT COUNT(*) FROM study_human_reviews WHERE status='ALL_THREE_AGREE_NO_USER_VERDICT'")==8
assert n("SELECT COUNT(*) FROM study_human_reviews WHERE status='USER_DEFERRED'")==1
assert n("SELECT COUNT(*) FROM study_runs WHERE experimental_family='RQ3_OWP14_ARCHIVED_SCAN_ARM'")==40
assert n("SELECT COUNT(*) FROM study_runs WHERE historical_revision_equivalence='NOT_VERIFIED'")==40
assert n("SELECT COUNT(*) FROM study_runs WHERE experimental_family='RQ3_OWP14_NEW_GENERATION_NONBLIND_20261031'")==2
violations=[tuple(r) for r in db.execute("PRAGMA foreign_key_check") if r[0].startswith("study_")]
assert not violations,violations[:10]
db.commit();v4.close();db.close()
(O/"EVIDENCE_COUNTS.json").write_text(json.dumps({
 "status":"EVIDENCE_AND_HUMAN_REVIEWS_COMPLETE","counts":actual,"patches":61,"raw_scans":68,
 "human_selected":41,"consensus_only":8,"deferred":1,"source_workbook_sha256":workbook_sha},indent=2)+"\n")
print(json.dumps({"status":"EVIDENCE_LINKS_COMPLETE","counts":actual},indent=2))
