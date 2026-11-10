#!/usr/bin/env python3
"""Non-destructive reviewer release candidate; source read-only, no original values overwritten."""
import sqlite3, re, csv, json, zipfile, hashlib, datetime
from pathlib import Path
root=Path.home()/"research_artifacts"
sp=root/"mcp_uploads/jobs/arno_d7_corrected_workbook_v4_20261031/output/ARNO_REVIEWER_WITH_CORRECTED_D7_ANNOTATIONS_V4_RELEASED.sqlite"
out=root/"mcp_uploads/jobs/arno_release_rc5_oct31/release"
out.mkdir(parents=True,exist_ok=True)
target=out/"ARNO_REVIEWER_RC5_MINIMIZED.sqlite"
assert not target.exists()
src=sqlite3.connect("file:"+str(sp)+"?mode=ro",uri=True)
src.row_factory=sqlite3.Row;src.execute("PRAGMA query_only=ON")
db=sqlite3.connect(str(target))
schema={
"research_cases":"case_id repository issue_url pr_url issue_number pr_number original_miner_status ai_cohort",
"mined_findings":"finding_id case_id pr_id scanner rule_id severity finding_type cwe file_path line description scanner_reported_introduced",
"canonical_findings":"finding_id case_id repository scanner rule_id description file_path severity qc_status reviewer_identity_status",
"experiment_runs":"run_id case_id root_id experiment_family condition recorded_status prompt_sha256 prompt_embedded experiment_stratum",
"patches":"patch_id run_id patch_sha256 patch_origin_status",
"scan_executions":"scan_id run_id scanner scanner_version target_rule scanner_result_summary execution_verified raw_result_sha256 raw_result_bytes",
"scan_metrics":"run_id case_id condition source_kind source_zip_sha256 before_findings after_findings newly_introduced newly_introduced_target remaining_target codeql_version codeql_suite after_sarif_sha256 patch_sha256 receipt_status functional_status provenance_status",
"scan_findings":"finding_id run_id case_id rule_id file_path line column severity message signature_sha256 new_vs_baseline matches_target_rule",
"owp_historical_results":"case_id condition scan_state source_snapshot_type codeql_version historical_target_rule newly_introduced_strict newly_introduced_conservative newly_introduced_target patch_sha256 functional_status scan_result_sha256 patch_bytes_match_status",
"screen65_results":"case_id source_snapshot_type scan_state scanner_suite before_total after_total new_strong new_weak historical_target_rules scan_result_sha256 link_to_generated_patch_status functional_status",
"evidence_artifacts":"evidence_id run_id case_id role sha256 original_bytes compression verification_status",
"archive_manifest":"case_id role sha256 original_bytes",
"evidence_sources":"source_key source_kind source_sha256 integrity_status bytes_in_master",
"root_decisions":"root_id case_id repository final_route final_tier final_route_confidence final_explanation_confidence chronology_status evidence_complete independent_review_status",
"classification_annotations":"case_id review_number implementation_final risk_final human_review_field_populated independent_review_status agent_tool agent_provenance",
"annotation_events":"event_id case_id dimension event_stage label_value",
"control_reviews":"blind_id priority corrected_fields human_verified review_provenance",
"blind_pair_reviews":"pair_id blind_pair_decision human_verified",
"canonical_review_status":"finding_id case_id reviewer_identity_status",
"new_rerun_provenance":"run_id case_id frozen_packet_sha256 patch_sha256 before_sarif_sha256 after_sarif_sha256 historical_O_recovered contributes_to_original_triple_count source_model provenance_status functional_status generation_date",
"human_review_batches":"batch_id source_workbook_sha256 source_sample_sha256 review_mode selected_verdicts consensus_without_user_verdict deferred_cases independent_blind_human_raters",
"human_review_labels":"batch_id review_id root_id case_id verdict_status original_route original_tier run_a_label run_b_label human_selected_route human_selected_tier comparison_to_original",
"scientific_limitations":"issue_id severity description"
}
rules={
"EMAIL":r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
"PRIVATE_KEY":r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
"SERVICE_TOKEN":r"\b(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
"PASS_LIKE":r"""(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"\n]{5,}['"]""",
"LOCAL_PATH":r"(?i)(?:/home-mscluster/[\w./-]+|/mnt/data/[\w./-]+|/Users/[\w./-]+|C:\\Users\\[\w\\.-]+)"
}
regex={k:re.compile(x) for k,x in rules.items()}
redactions={x:0 for x in rules}
redact_index=[]
def sanitize(table,column,id,v):
 if not isinstance(v,str):return v
 for kind,r in regex.items():
  v,n=r.subn("[REDACTED_"+kind+"]",v)
  if n:
   redactions[kind]+=n
   redact_index.append([table,column,hashlib.sha256(str(id).encode()).hexdigest()[:20],kind,n])
 return v
counts={}
for tab,raw in schema.items():
 cols=raw.split()
 info={r["name"]:r["type"] or "TEXT" for r in src.execute('PRAGMA table_info("'+tab+'")')}
 for k in cols:assert "BLOB" not in info[k].upper(),(tab,k)
 db.execute('CREATE TABLE "'+tab+'" ('+','.join('"'+x+'" '+info[x] for x in cols)+')')
 sql='SELECT '+','.join('"'+x+'"' for x in cols)+' FROM "'+tab+'"'
 vals=[]
 for i,row in enumerate(src.execute(sql),1):
  new=[]
  for key in cols:
   v=row[key]
   assert not isinstance(v,bytes),(tab,key)
   new.append(sanitize(tab,key,row[cols[0]],v))
  vals.append(tuple(new))
  if len(vals)==300:
   db.executemany('INSERT INTO "'+tab+'" VALUES ('+','.join('?' for x in cols)+')',vals);vals=[]
 if vals:db.executemany('INSERT INTO "'+tab+'" VALUES ('+','.join('?' for x in cols)+')',vals)
 cnt=db.execute('SELECT COUNT(*) FROM "'+tab+'"').fetchone()[0]
 assert cnt==src.execute('SELECT COUNT(*) FROM "'+tab+'"').fetchone()[0],tab
 counts[tab]=cnt
for t,col in [("research_cases","case_id"),("mined_findings","case_id"),("canonical_findings","case_id"),("experiment_runs","run_id"),("experiment_runs","case_id"),("patches","run_id"),("scan_executions","run_id"),("scan_metrics","run_id"),("scan_findings","run_id"),("scan_findings","case_id"),("root_decisions","root_id"),("human_review_labels","root_id"),("evidence_artifacts","run_id")]:
 db.execute('CREATE INDEX idx_'+t+'_'+col+' ON "'+t+'" ("'+col+'")')
db.executescript("""
CREATE VIEW cases_and_warnings AS SELECT c.case_id,c.repository,c.issue_url,c.pr_url,
 f.finding_id,f.scanner,f.rule_id,f.severity,f.file_path,f.line,f.description
 FROM research_cases c JOIN mined_findings f ON c.case_id=f.case_id;
CREATE VIEW experiment_to_scanner AS SELECT e.run_id,e.case_id,e.condition,e.experiment_stratum,
 p.patch_id,p.patch_sha256,p.patch_origin_status,m.before_findings,m.after_findings,
 m.newly_introduced,m.newly_introduced_target,m.functional_status,m.provenance_status
 FROM experiment_runs e LEFT JOIN patches p ON p.run_id=e.run_id LEFT JOIN scan_metrics m ON m.run_id=e.run_id;
CREATE VIEW human_vs_reference AS SELECT r.root_id,r.case_id,r.final_route,r.final_tier,
 h.verdict_status,h.human_selected_route,h.human_selected_tier,h.comparison_to_original
 FROM root_decisions r LEFT JOIN human_review_labels h ON h.root_id=r.root_id;
CREATE TABLE release_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
""")
meta={
"release_id":"ARNO_RC5_MINIMIZED_20261031",
"release_status":"NOT_CLEARED_FOR_PUBLIC_UNRESTRICTED_DISTRIBUTION",
"annotations":"41_POSTHOC_HUMAN_SELECTED_AI_ASSISTED_8_CONSENSUS_ONLY_1_DEFERRED",
"independent_inter_rater":"NOT_AVAILABLE_ONE_HUMAN_ONLY",
"corrected_workbook_sha256":"e2370e44b64a051db061642e271e671310fba19969af24421291214fa339925e",
"raw_patches":"NOT_INCLUDED_COMPANION_ARCHIVE_REQUIRED",
"raw_evidence":"NOT_INCLUDED_COMPANION_ARCHIVE_REQUIRED",
"original_historical_triples":"12","fresh_nonblind_owp_runs":"2_SEPARATE",
"immutable_source_master":"YES","immutable_prior_reviewer_v4":"YES"
}
db.executemany("INSERT INTO release_metadata VALUES (?,?)",meta.items())
def n(s):return db.execute(s).fetchone()[0]
checks=dict(quick_check=n("PRAGMA quick_check"),
 human=n("SELECT COUNT(*) FROM human_review_labels"),
 selected=n("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_ADJUDICATED'"),
 consensus=n("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='ALL_THREE_AGREE_NO_USER_VERDICT'"),
 deferred=n("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_DEFERRED'"),
 introduced_findings=n("SELECT COUNT(*) FROM scan_findings"),
 historic_owp=n("SELECT COUNT(*) FROM owp_historical_results"),
 new_nonblind=n("SELECT COUNT(*) FROM new_rerun_provenance"),
 patch_orphans=n("SELECT COUNT(*) FROM patches p LEFT JOIN experiment_runs e ON e.run_id=p.run_id WHERE e.run_id IS NULL"),
 run_case_orphans=n("SELECT COUNT(*) FROM experiment_runs e LEFT JOIN research_cases c ON c.case_id=e.case_id WHERE e.case_id IS NOT NULL AND c.case_id IS NULL"),
 nonblind_in_original_count=n("SELECT COUNT(*) FROM new_rerun_provenance WHERE contributes_to_original_triple_count=1"))
assert checks["quick_check"]=="ok" and (checks["human"],checks["selected"],checks["consensus"],checks["deferred"])==(50,41,8,1)
assert checks["introduced_findings"]==5491 and checks["historic_owp"]==40 and checks["new_nonblind"]==2
assert checks["patch_orphans"]==0 and checks["run_case_orphans"]==0 and checks["nonblind_in_original_count"]==0
db.commit();db.execute("VACUUM");db.close();src.close()
sha=hashlib.sha256(target.read_bytes()).hexdigest()
report={"status":"RC5_RESTRICTED_CANDIDATE_VERIFIED_NOT_PUBLIC","path":str(target),"size":target.stat().st_size,
"sha256":sha,"row_counts":counts,"quality_checks":checks,"redactions":redactions,
"unresolved_gates":["Manual review of sensitive content flags","Original 42GB vault not fully screened",
"Raw patch/SARIF/prompt reproducibility companion not yet cleared","Paper claims/denominators not yet verified",
"No second human annotator; post-hoc AI-assisted human review only"],"master_unchanged":True,"reviewer_v4_unchanged":True}
(out/"RELEASE_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
with (out/"SENSITIVE_REDACTIONS_PRIVATE.csv").open("w",newline="") as f:
 w=csv.writer(f);w.writerow(["table","column","hash_of_key","category","occurrences"]);w.writerows(redact_index)
with (out/"DATA_DICTIONARY.csv").open("w",newline="") as f:
 w=csv.writer(f);w.writerow(["table","column","source"]);[w.writerow([t,c,"V4 "+t]) for t,s in schema.items() for c in s.split()]
(out/"REVIEWER_QUERIES.sql").write_text("""SELECT * FROM cases_and_warnings WHERE case_id=3375;
SELECT * FROM experiment_to_scanner ORDER BY case_id,run_id;
SELECT * FROM human_vs_reference WHERE verdict_status IS NOT NULL;
SELECT * FROM owp_historical_results ORDER BY case_id,condition;
SELECT * FROM scientific_limitations ORDER BY severity;
""")
(out/"README.md").write_text("""# ARNO evidence-oriented SQLite RC5 (restricted candidate)

This publication-facing projection prioritises case links, scanner findings, intervention outcomes, source SHA checksums, root labels and annotation status. Internal workflow tables and raw binary payloads are not copied. The original Wits master and previous V4 reviewer database remain unchanged.

Static-analysis warnings are not confirmed security vulnerabilities. Clean scanner results do not establish functional correctness. There are 12 historical matched O/W/P triples and two separate nonblind GPT-6 reruns, not 14 original triples.

The corrected annotations comprise 41 post-hoc AI-assisted user-selected decisions, 8 consensus-only entries lacking a separate human verdict and 1 deferred case. There is no second independent human annotator or human-human agreement coefficient. Full rationale/evidence remains in the separately hashed corrected annotation sidecar.

This RC5 database is NOT READY for unrestricted public distribution. The full 42GB evidence archive, licence/disclosure and paper-claim checks are incomplete. Original patch/evidence bytes are withheld pending content review. Redactions in retained text are marked explicitly, never silently. See RELEASE_REPORT.json and original SHA evidence keys.
""")
with zipfile.ZipFile(out/"ARNO_REVIEWER_RC5_RESTRICTED.zip","w",zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for f in ["ARNO_REVIEWER_RC5_MINIMIZED.sqlite","RELEASE_REPORT.json","DATA_DICTIONARY.csv","REVIEWER_QUERIES.sql","README.md"]:z.write(out/f,f)
print(json.dumps(dict(status="READY_RESTRICTED",rows=counts,checks=checks,redactions=redactions,zip_bytes=(out/"ARNO_REVIEWER_RC5_RESTRICTED.zip").stat().st_size),indent=2))
