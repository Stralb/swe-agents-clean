#!/usr/bin/env python3
"""Create non-public, read-only-source reviewer database from live Wits ARNO master."""
import sqlite3,hashlib,json,csv,re,datetime,zipfile,os
from pathlib import Path
from urllib.parse import quote
R=Path.home()/"research_artifacts"
MASTER=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_reviewer_release_20261031_v3/output"
OUT.mkdir(parents=True,exist_ok=False)
FILE=OUT/"ARNO_REVIEWER_RESTRICTED_CANDIDATE.sqlite"
db=sqlite3.connect(str(FILE),timeout=180)
db.execute("ATTACH DATABASE ? AS src",("file:"+quote(str(MASTER))+"?mode=ro",))
db.create_function("sha256",1,lambda x:hashlib.sha256(x).hexdigest() if x is not None else None)
views={
"research_cases":"""SELECT c.id case_id,r.full_name repository,i.url issue_url,p.url pr_url,
i.number issue_number,p.number pr_number,c.status original_miner_status,c.ai_cohort
FROM src.cases c JOIN src.repos r ON c.repo_id=r.id
JOIN src.issues i ON c.issue_id=i.id JOIN src.pull_requests p ON c.pr_id=p.id""",
"mined_findings":"""SELECT id finding_id,case_id,pr_id,scanner,rule_id,severity,finding_type,cwe,
file_path,line,description,introduced scanner_reported_introduced
FROM src.scanner_findings""",
"canonical_findings":"""SELECT canonical_finding_id finding_id,case_id,repository,scanner,rule_id,
description,primary_file file_path,severity,frozen_qc_status qc_status,
reviewer_identity_status FROM src.arno_new70_final_findings""",
"experiment_runs":"""SELECT run_id,case_id,root_id,experiment_family,treatment condition,
status recorded_status,run_metadata_json reproducibility_metadata,
CASE WHEN LENGTH(COALESCE(prompt_blob,x''))>0 THEN sha256(prompt_blob) END prompt_sha256,
CASE WHEN LENGTH(COALESCE(prompt_blob,x''))>0 THEN 1 ELSE 0 END prompt_embedded,
CASE WHEN experiment_family='RQ3_OWP14_NEW_GENERATION_NONBLIND_20261031' THEN 'NEW_NONBLIND_EXPLORATORY'
WHEN experiment_family='RQ3_OWP14_ARCHIVED_SCAN_ARM' THEN 'HISTORICAL_ARCHIVED_UNREEXECUTED'
ELSE 'OTHER_RESEARCH_RUN' END experiment_stratum
FROM src.arno_experiment_runs""",
"patches":"""SELECT patch_id,run_id,content_sha256 patch_sha256,patch_blob patch_bytes,
authenticity_status patch_origin_status,patch_uri original_patch_locator
FROM src.arno_generated_patches""",
"scan_executions":"""SELECT scan_id,run_id,scanner,scanner_version,rule_id target_rule,
result_json scanner_result_summary,execution_verified,
CASE WHEN raw_result_blob IS NULL THEN NULL ELSE sha256(raw_result_blob) END raw_result_sha256,
CASE WHEN raw_result_blob IS NULL THEN 0 ELSE LENGTH(raw_result_blob) END raw_result_bytes
FROM src.arno_experiment_scans""",
"scan_metrics":"""SELECT run_id,case_id,method condition,source_kind,source_zip_sha256,
baseline_total before_findings,after_total after_findings,new_vs_baseline newly_introduced,
historical_p1_new newly_introduced_target,historical_p1_remaining remaining_target,
codeql_version,codeql_suite,sarif_sha256 after_sarif_sha256,patch_sha256,
receipt_status,functional_status,provenance_status
FROM src.arno_chat_codeql_metrics""",
"scan_findings":"""SELECT finding_id,run_id,case_id,rule_id,file_path,line,column,
level severity,message,signature_sha256,new_vs_baseline,
matches_historical_p1 matches_target_rule
FROM src.arno_chat_codeql_findings""",
"owp_historical_results":"""SELECT case_id,arm condition,scan_state,
source_snapshot_type,codeql_version,historical_target_rule,
new_strong_count newly_introduced_strict,
new_conservative_count newly_introduced_conservative,
target_new_strong newly_introduced_target,patch_sha256,functional_status,
result_sha256 scan_result_sha256,patch_bytes_match_status
FROM src.arno_rq3_owp14_run_scans""",
"screen65_results":"""SELECT case_id,source_snapshot_type,scan_state,scanner_suite,
before_total,after_total,new_strong,new_weak,historical_target_rules,
result_sha256 scan_result_sha256,link_to_generated_patch_status,
functional_status FROM src.arno_rq3_codeql_screen65_original""",
"evidence_artifacts":"""SELECT artifact_id evidence_id,run_id,case_id,role,sha256,original_bytes,
compression,content_zlib compressed_evidence_bytes,verification_status
FROM src.arno_chat_evidence_objects""",
"archive_manifest":"""SELECT archive_name,member_path,case_id,role,sha256,original_bytes
FROM src.arno_archive_vault_members""",
"evidence_sources":"""SELECT source_key,source_kind,source_sha256,verification integrity_status,
CASE WHEN embedded_bytes IS NULL THEN 0 ELSE 1 END bytes_in_master
FROM src.arno_sources""",
"classification_annotations":"""SELECT case_id,review_number,implementation_final,risk_final,
CASE WHEN trim(COALESCE(risk_human_review,''))='' THEN 0 ELSE 1 END human_review_field_populated,
'NO_INDEPENDENT_HUMAN_ATTESTATION_DOCUMENTED' independent_review_status,
agent_tool,agent_provenance FROM src.arno_classifications""",
"annotation_events":"""SELECT event_id,case_id,dimension,event_stage,label_value
FROM src.arno_annotation_events""",
"control_reviews":"""SELECT blind_id,priority,corrected_fields,reason,human_verified,
review_provenance FROM src.arno_rq2_c5_corrections""",
"blind_pair_reviews":"""SELECT pair_id,blind_pair_decision,human_verified
FROM src.arno_rq3_t1_blind_pairs""",
"canonical_review_status":"""SELECT canonical_finding_id finding_id,case_id,reviewer_identity_status
FROM src.arno_new70_final_findings""",
"root_decisions":"""SELECT root_id,case_id,repository,final_route,final_tier,
final_route_confidence,final_explanation_confidence,chronology_status,
evidence_complete,'HUMAN_IDENTITY_NOT_ATTESTED' independent_review_status
FROM src.arno_d7_final_roots_342""",
"new_rerun_provenance":"""SELECT run_id,case_id,frozen_packet_sha256,patch_sha256,
before_sarif_sha256,after_sarif_sha256,
historical_O_recovered,contributes_to_original_triple_count,
source_model,provenance_status,functional_status,generation_date
FROM src.arno_owp14_fresh_o_reruns_20261031"""
}
counts={}
for table,select in views.items():
 db.execute("CREATE TABLE "+table+" AS "+select)
 counts[table]=db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
 print(table,counts[table],flush=True)
expected={"research_cases":3809,"mined_findings":1842,"canonical_findings":237,"experiment_runs":68,"patches":61,
"scan_executions":68,"scan_findings":5491,"owp_historical_results":40,"screen65_results":65,
"classification_annotations":122,"annotation_events":494,"control_reviews":42,
"blind_pair_reviews":29,"canonical_review_status":237,"root_decisions":342,"new_rerun_provenance":2}
for k,v in expected.items():assert counts[k]==v,(k,counts[k],v)
for t,cols in [
 ("research_cases","case_id"),("mined_findings","case_id,rule_id"),
 ("canonical_findings","case_id,rule_id"),("experiment_runs","run_id"),
 ("patches","run_id"),("scan_executions","run_id"),("scan_metrics","run_id"),
 ("scan_findings","run_id,rule_id"),("scan_findings","case_id,rule_id,new_vs_baseline"),
 ("evidence_artifacts","run_id,role"),("archive_manifest","case_id,role"),
 ("classification_annotations","case_id"),("root_decisions","case_id")
]:db.execute("CREATE INDEX i_"+str(abs(hash(t+cols))%1000000000)+" ON "+t+"("+cols+")")
db.execute("CREATE TABLE release_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
metadata={
"status":"RESTRICTED_CANDIDATE_NOT_CLEARED_FOR_PUBLICATION",
"source":"LIVE_WITS_MASTER_READ_ONLY",
"master_edited":"NO",
"scope":"CASE_FINDINGS_PATCH_SCAN_EVIDENCE_ANNOTATIONS",
"original_owp_complete_triples":"12",
"nonblind_new_owp_runs":"2; NOT HISTORICAL",
"scanner_interpretation":"SCANNER_FINDING_NOT_PROOF_OF_EXPLOITABILITY",
"human_review_claim":"NOT_ATTESTED",
"methodology":"NARRATIVE_IN_PAPER_REPRO_METADATA_IN_DATABASE",
"exclusion_policy":"INTERNAL_PIPELINE_METADATA_EXCLUDED_BUT_SCIENTIFIC_LIMITATIONS_RETAINED",
"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()
}
db.executemany("INSERT INTO release_metadata VALUES (?,?)",metadata.items())
issues=[
("HUMAN_FIRST122","CRITICAL","122 of 122 risk_human_review fields are empty."),
("HUMAN_C5","CRITICAL","0 of 42 matched-control corrections have human_verified=1."),
("HUMAN_T1","CRITICAL","0 of 29 blind-pair decisions have human_verified=1."),
("HUMAN_NEW70","CRITICAL","237 canonical finding source QC records do not attest independent reviewer identity."),
("HUMAN_D7","HIGH","342 final root decisions do not establish independent human adjudicator identity."),
("OWP_INCOMPLETE","HIGH","Original OWP experiment has 12 complete triples; two historical O-arm results missing."),
("RERUN_DIFFERENT","HIGH","2026-10-31 GPT-6 O reruns non-blind and cannot be historical imputations."),
("FUNCTIONAL_UNVERIFIED","HIGH","CodeQL scanner success alone does not verify functional correctness."),
("PATCH_PROVENANCE","HIGH","Patch SHA verification does not independently authenticate original model/tool origin."),
("SCANNER_LIMITS","HIGH","Scanner findings are not proof of exploitable vulnerabilities."),
("PRIVATE_RELEASE","HIGH","Privacy and disclosure review required for source paths, patch bytes, scanner messages and evidence blobs."),
("EXTERNAL_EVIDENCE","MEDIUM","Full original raw scanner reports and 42GB evidence vault not all included as portable artifacts.")
]
db.execute("CREATE TABLE scientific_limitations(issue_id TEXT PRIMARY KEY,severity TEXT,description TEXT)")
db.executemany("INSERT INTO scientific_limitations VALUES (?,?,?)",issues)
db.commit()
assert db.execute("PRAGMA quick_check").fetchone()[0]=="ok"
assert db.execute("SELECT COUNT(*) FROM control_reviews WHERE human_verified=1").fetchone()[0]==0
assert db.execute("SELECT COUNT(*) FROM new_rerun_provenance WHERE contributes_to_original_triple_count<>0").fetchone()[0]==0
db.execute("DETACH DATABASE src")
db.close()
# Names, columns and source metadata are reviewed by category; no original text altered.
src=sqlite3.connect("file:"+quote(str(MASTER))+"?mode=ro",uri=True)
term_categories=[
("reviewer_internal",r"peer.?review|supervisor|professor|examiner"),
("operational_recovery",r"recovery|recovered|restore|supersession|postmerge|handoff"),
("dated_schema",r"20[12][0-9][01][0-9][0-3][0-9]"),
("research_staging",r"qc|audit|prelim|stage|phase"),
("provenance_limitations",r"not_verified|missing|provisional|unverified|failed"),
("sensitive_terms",r"private|malicious|risk|unsafe")
]
nflags=[]
cflags=[]
for name,typ in src.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
 for cat,pat in term_categories:
  if re.search(pat,name,re.I):nflags.append(dict(name=name,type=typ,category=cat,action="REVIEWER_ALIAS_ONLY_KEEP_MASTER"))
 if typ=="table":
  q=name.replace('"','""')
  for col in src.execute('PRAGMA table_info("'+q+'")'):
   for cat,pat in term_categories:
    if re.search(pat,col[1],re.I):cflags.append(dict(table=name,column=col[1],category=cat))
label_hits=[]
for source_key,source_kind,verification,notes in src.execute("SELECT source_key,source_kind,verification,notes FROM arno_sources"):
 txt=" ".join(str(x or "") for x in (source_kind,verification,notes))
 matched=[cat for cat,pat in term_categories if re.search(pat,txt,re.I)]
 if matched:label_hits.append(dict(source_key=source_key,classes=matched))
src.close()
def filehash(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
audit=dict(status="RESTRICTED_CANDIDATE_BUILT",database_path=str(FILE),bytes=FILE.stat().st_size,
 sha256=filehash(FILE),source_master_bytes=MASTER.stat().st_size,counts=counts,
 explicit_human_review_verified=0,scientific_limitations=issues,name_flags=nflags,
 column_name_flags=cflags,source_metadata_flag_classes=label_hits,
 privacy_cleared=False,master_mutated=False)
(OUT/"AUDIT_REPORT.json").write_text(json.dumps(audit,indent=2)+"\n")
with (OUT/"SCHEMA_NAME_TRIAGE.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["name","type","category","action"]);w.writeheader();w.writerows(nflags)
(OUT/"README.md").write_text("""# ARNO restricted reviewer database candidate

Not approved for public release. Source Wits master remains unchanged.

The candidate prioritizes case -> scanner finding -> experiment -> patch -> scan result -> warning -> evidence queries.
Source pipeline/history tables are excluded from the reviewer-facing schema, but ALL scientifically material warning observations and uncertainty statuses remain.

Human-review provenance is not attested in the original 122 cases, 42 C5 corrections, 29 T1 blind pairs, 237 NEW70 finding decisions and 342 D7 root decisions. A completed classification is not evidence of independent human review.

Before publishing: verify privacy/security disclosure of patch bodies and warning messages, raw SARIF and agent prompt artifact availability, reviewer agreement and claim consistency. The methodology narrative belongs in the manuscript; reproducibility settings stay in the release.

The original master provides a larger 42GB archival corpus, not included in this compact file. No synchronization to Hugging Face or user's laptop was performed.
""")
with zipfile.ZipFile(OUT/"ARNO_REVIEWER_RESTRICTED_CANDIDATE.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n in [FILE.name,"AUDIT_REPORT.json","SCHEMA_NAME_TRIAGE.csv","README.md"]:
  z.write(OUT/n,arcname=n)
print("SUCCESS",json.dumps({"size":FILE.stat().st_size,"archive":(OUT/"ARNO_REVIEWER_RESTRICTED_CANDIDATE.zip").stat().st_size,"counts":counts}),flush=True)
