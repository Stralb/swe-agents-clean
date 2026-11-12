#!/usr/bin/env python3
"""Unify initial and subsequent research cohorts in the NEW immutable-master snapshot."""
import sqlite3,hashlib,json
from pathlib import Path
O=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output"
assert (O/"BACKUP_VERIFICATION.json").exists(),"Backup not verified"
db=O/"ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
assert db.exists()
con=sqlite3.connect(str(db),timeout=180)
con.row_factory=sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")
assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='study_cases'").fetchone(),"Do not alter existing unified layer"
con.executescript("""
CREATE TABLE study_cases(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),
 collection_phase TEXT NOT NULL CHECK(collection_phase IN('INITIAL_COLLECTION','SUBSEQUENT_EXTENSION')),
 source_table TEXT NOT NULL,review_number INTEGER NOT NULL,
 protocol_note TEXT NOT NULL,UNIQUE(collection_phase,review_number));
CREATE TABLE study_producing_changes(
 change_key TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES study_cases(case_id),
 source_change_id TEXT NOT NULL,root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
 attribution TEXT NOT NULL,attribution_basis TEXT,
 source_key TEXT NOT NULL,source_table TEXT NOT NULL,UNIQUE(source_table,source_change_id));
CREATE TABLE study_findings(
 finding_key TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES study_cases(case_id),
 original_finding_id TEXT NOT NULL,scanner TEXT,rule_id TEXT,severity TEXT,
 description TEXT,mapping_status TEXT NOT NULL CHECK(mapping_status IN('MAPPED','NOT_ISOLATED')),
 change_key TEXT REFERENCES study_producing_changes(change_key),
 source_row_sha256 TEXT NOT NULL,source_table TEXT NOT NULL,mapping_note TEXT,
 CHECK((mapping_status='MAPPED' AND change_key IS NOT NULL) OR
       (mapping_status='NOT_ISOLATED' AND change_key IS NULL)),
 UNIQUE(source_table,original_finding_id));
CREATE TABLE study_classifications(
 case_id INTEGER PRIMARY KEY REFERENCES study_cases(case_id),
 source_table TEXT NOT NULL,implementation_label TEXT,risk_label TEXT,
 implementation_coverage TEXT NOT NULL,
 independent_human_review TEXT NOT NULL,review_number INTEGER NOT NULL);
CREATE TABLE study_roots(
 root_id TEXT PRIMARY KEY REFERENCES arno_d7_final_roots_342(root_id),
 case_id INTEGER NOT NULL REFERENCES study_cases(case_id),route TEXT NOT NULL,tier TEXT NOT NULL,
 chronology TEXT,evidence_complete TEXT,origin_review_status TEXT NOT NULL);
""")
con.execute("BEGIN IMMEDIATE")
con.execute("""INSERT INTO study_cases SELECT case_id,'INITIAL_COLLECTION','arno_classifications',
review_number,'First stage: no independent holdout claim' FROM arno_classifications""")
con.execute("""INSERT INTO study_cases SELECT case_id,'SUBSEQUENT_EXTENSION','arno_new70_source_inputs',
review_number,'Added during study development: chronology retained' FROM arno_new70_source_inputs""")
con.execute("""INSERT INTO study_producing_changes
SELECT CASE WHEN cohort='original122' THEN 'INITIAL:' ELSE 'EXTENSION:' END||producing_change_id,
 case_id,producing_change_id,root_id,attribution,attribution_basis,source_key,
 'arno_frozen_broad_attribution'
FROM arno_frozen_broad_attribution""")
def digest(raw):return hashlib.sha256((raw or "").encode()).hexdigest()
for x in con.execute("""SELECT a.canonical_finding_id id,a.case_id,a.scanner,a.rule_id,a.severity,
a.finding_description,a.row_json,b.mapping_status,b.source_producing_change_id,b.changed_locations
FROM arno_original_step1_detail a JOIN arno_original_step2_detail b
ON a.canonical_finding_id=b.canonical_finding_id""").fetchall():
 assert x["mapping_status"]=="Mapped"
 con.execute("INSERT INTO study_findings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 "INITIAL:"+x["id"],x["case_id"],x["id"],x["scanner"],x["rule_id"],x["severity"],
 x["finding_description"],"MAPPED","INITIAL:"+x["source_producing_change_id"],
 digest(x["row_json"]),"arno_original_step1_detail",x["changed_locations"]))
for x in con.execute("""SELECT a.canonical_finding_id id,a.case_id,a.scanner,a.rule_id,a.severity,
a.description,a.original_row_json,b.mapping_status,b.producing_change_id,b.no_mapping_reason
FROM arno_new70_final_findings a JOIN arno_new70_final_finding_maps b
ON a.canonical_finding_id=b.canonical_finding_id""").fetchall():
 ismapped=x["mapping_status"]=="Mapped"
 con.execute("INSERT INTO study_findings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 "EXTENSION:"+x["id"],x["case_id"],x["id"],x["scanner"],x["rule_id"],x["severity"],
 x["description"],"MAPPED" if ismapped else "NOT_ISOLATED",
 "EXTENSION:"+x["producing_change_id"] if ismapped else None,digest(x["original_row_json"]),
 "arno_new70_final_findings",x["no_mapping_reason"]))
con.execute("""INSERT INTO study_classifications
SELECT case_id,'arno_classifications',implementation_final,risk_final,
'IMPLEMENTATION_LABEL_AVAILABLE','INDEPENDENT_HUMAN_NOT_ATTESTED',review_number
FROM arno_classifications""")
con.execute("""INSERT INTO study_classifications
SELECT r.case_id,'arno_new70_phase9_risk',NULL,r.final_risk_label,
'IMPLEMENTATION_LABEL_NOT_COLLECTED_IN_MATCHING_FIELD',
'INDEPENDENT_HUMAN_NOT_ATTESTED',s.review_number
FROM arno_new70_phase9_risk r JOIN arno_new70_source_inputs s ON r.case_id=s.case_id""")
con.execute("""INSERT INTO study_roots
SELECT root_id,case_id,final_route,final_tier,chronology_status,evidence_complete,
'FROZEN_SOURCE_NOT_INDEPENDENT_HUMAN'
FROM arno_d7_final_roots_342""")
con.executescript("""
CREATE INDEX study_findings_case_idx ON study_findings(case_id);
CREATE INDEX study_findings_change_idx ON study_findings(change_key);
CREATE INDEX study_changes_case_idx ON study_producing_changes(case_id);
CREATE INDEX study_roots_case_idx ON study_roots(case_id);
CREATE VIEW study_paper_findings AS
SELECT f.finding_key,f.case_id,c.collection_phase,f.scanner,f.rule_id,f.severity,
f.description,f.mapping_status,p.change_key,p.root_id,p.attribution
FROM study_findings f JOIN study_cases c ON f.case_id=c.case_id
LEFT JOIN study_producing_changes p ON f.change_key=p.change_key;
""")
def n(q):return con.execute(q).fetchone()[0]
results={t:n("SELECT count(*) FROM "+t) for t in
["study_cases","study_producing_changes","study_findings","study_classifications","study_roots"]}
assert results=={"study_cases":192,"study_producing_changes":455,"study_findings":842,
"study_classifications":192,"study_roots":342},results
assert n("SELECT count(*) FROM study_findings WHERE mapping_status='MAPPED'")==781
assert n("SELECT count(*) FROM study_findings WHERE mapping_status='NOT_ISOLATED'")==61
assert n("SELECT count(*) FROM study_findings WHERE mapping_status='MAPPED' AND change_key NOT IN (SELECT change_key FROM study_producing_changes)")==0
violations=[tuple(r) for r in con.execute("PRAGMA foreign_key_check") if r[0].startswith("study_")]
assert not violations,violations[:10]
con.commit()
(O/"CORE_COUNTS.json").write_text(json.dumps({"core_status":"PASS","counts":results,"mapped":781,"unmapped":61,"source_original_unchanged":True},indent=2)+"\n")
print(json.dumps({"stage":"CORE_COMPLETE","counts":results},indent=2))
con.close()
