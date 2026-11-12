#!/usr/bin/env python3
"""Independently validate and package completed non-public reviewer candidate, without touching source."""
import sqlite3,hashlib,json,zipfile,csv,datetime
from pathlib import Path
from urllib.parse import quote
R=Path.home()/"research_artifacts"
src=R/"mcp_uploads/jobs/arno_reviewer_release_20261031_v3/output/ARNO_REVIEWER_RESTRICTED_CANDIDATE.sqlite"
OUT=R/"mcp_uploads/jobs/arno_reviewer_candidate_finalize_20261031_v1/output"
OUT.mkdir(parents=True,exist_ok=False)
c=sqlite3.connect("file:"+quote(str(src))+"?mode=ro",uri=True,timeout=60)
c.execute("PRAGMA query_only=ON")
ok=c.execute("PRAGMA quick_check").fetchone()[0]
assert ok=="ok",ok
tables=[x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
expected={"research_cases":3809,"mined_findings":1842,"canonical_findings":237,"experiment_runs":68,"patches":61,"scan_executions":68,"scan_metrics":28,"scan_findings":5491,
"owp_historical_results":40,"screen65_results":65,"evidence_artifacts":268,"archive_manifest":4610,"evidence_sources":118,
"classification_annotations":122,"annotation_events":494,"control_reviews":42,"blind_pair_reviews":29,"canonical_review_status":237,
"root_decisions":342,"new_rerun_provenance":2,"scientific_limitations":12}
counts={}
for name,n in expected.items():
 counts[name]=c.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]
 assert counts[name]==n,(name,counts[name],n)
assert c.execute("SELECT COUNT(*) FROM classification_annotations WHERE human_review_field_populated=1").fetchone()[0]==0
assert c.execute("SELECT COUNT(*) FROM control_reviews WHERE human_verified=1").fetchone()[0]==0
assert c.execute("SELECT COUNT(*) FROM blind_pair_reviews WHERE human_verified=1").fetchone()[0]==0
assert c.execute("SELECT COUNT(*) FROM new_rerun_provenance WHERE contributes_to_original_triple_count!=0").fetchone()[0]==0
sha=hashlib.sha256()
with src.open("rb") as f:
 for chunk in iter(lambda:f.read(2**20),b""):sha.update(chunk)
report={"status":"RESTRICTED_INTERNAL_CANDIDATE_VERIFIED","public_release_ready":False,
"database":str(src),"bytes":src.stat().st_size,"sha256":sha.hexdigest(),"tables":len(tables),
"row_counts":counts,"quick_check":"ok",
"human_annotation_verification":"NOT_ATTESTED_IN_SOURCE_FIELDS",
"original_study_OWP":"40 historical scans, 12 complete triples; two original O missing",
"new_rerun_status":"two separate nonblind GPT6 reruns; not historical replacements",
"privacy_and_disclosure_screen":"NOT_COMPLETED",
"full_raw_sarif_companion":"NOT_INCLUDED_AND_NOT_YET_RELEASE_CERTIFIED",
"source_master_modified":"NO"}
(OUT/"VALIDATION_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
(OUT/"README_FIRST.md").write_text("""# ARNO restricted reviewer DB candidate (NOT FOR PUBLIC RELEASE)

Validated candidate generated read-only from the Wits master (original source unchanged).
This candidate provides 22 stable interface tables for querying cases, scanner findings,
experiments, patch bytes, CodeQL results, evidence artifacts, provenance, and annotations.

**Human review caveat**: no independent human-review attestation is established by the
original 122 risk review fields, 42 C5 flags, 29 T1 flags, 237 NEW70 identity statuses,
or 342 D7 final root decisions. None are falsely elevated to verified human review.

**Scientific caveat**: 12 original matched O/W/P triples; two fresh GPT-6 reruns
are separate exploratory evidence. Functional correctness is unverified.
Static analysis warnings do not establish exploited vulnerabilities.

This version is RESTRICTED because raw patches, message strings, and evidence
may contain disclosure-sensitive information. Public release requires content-level
privacy/secret scan, complete raw SARIF and prompts by SHA, and paper-claim audit.
Methodology narrative can reside in the paper; machine reproducibility metadata remains.
""")
(OUT/"REVIEWER_QUERIES.sql").write_text("""-- Reviewer-friendly run -> patch -> scanner result lookup
SELECT c.case_id,c.repository,r.run_id,r.condition,r.experiment_stratum,
       p.patch_sha256,m.before_findings,m.after_findings,m.newly_introduced,
       m.provenance_status,m.functional_status
FROM research_cases AS c
JOIN experiment_runs AS r ON r.case_id=c.case_id
LEFT JOIN patches AS p ON p.run_id=r.run_id
LEFT JOIN scan_metrics AS m ON m.run_id=r.run_id
WHERE c.case_id IN (8461,15151)
ORDER BY c.case_id,r.run_id;

-- Newly introduced warnings; complete baseline findings remain queryable
SELECT run_id,case_id,rule_id,file_path,line,severity,message
FROM scan_findings WHERE new_vs_baseline=1;

-- Explicitly missing independent review evidence
SELECT COUNT(*) total,SUM(human_review_field_populated) recorded_review_fields
FROM classification_annotations;

-- Evidence by run and content hash
SELECT run_id,role,sha256,original_bytes,verification_status
FROM evidence_artifacts WHERE run_id IS NOT NULL ORDER BY run_id,role;

SELECT * FROM scientific_limitations ORDER BY severity,issue_id;
""")
with (OUT/"SCHEMA_INVENTORY.csv").open("w",newline="") as f:
 w=csv.writer(f);w.writerow(["table","columns"])
 for table in tables:
  escaped=table.replace('"','""')
  cols=[row[1] for row in c.execute('PRAGMA table_info("'+escaped+'")')]
  w.writerow([table,", ".join(cols)])
c.close()
zipfile_path=OUT/"ARNO_REVIEWER_RESTRICTED_CANDIDATE_20261031.zip"
with zipfile.ZipFile(zipfile_path,"w",zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 z.write(src,arcname=src.name)
 for name in ["VALIDATION_REPORT.json","README_FIRST.md","REVIEWER_QUERIES.sql","SCHEMA_INVENTORY.csv"]:
  z.write(OUT/name,arcname=name)
print(json.dumps(dict(status="VERIFIED_AND_PACKAGED",zip_path=str(zipfile_path),zip_bytes=zipfile_path.stat().st_size,
database_sha256=report["sha256"],counts=counts),indent=2),flush=True)
