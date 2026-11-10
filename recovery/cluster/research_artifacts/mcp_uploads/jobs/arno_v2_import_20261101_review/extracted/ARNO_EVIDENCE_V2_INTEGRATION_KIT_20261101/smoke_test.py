#!/usr/bin/env python3
"""Minimal schema-level test without using private Wits data."""
import sqlite3
import wits_integrate_v2 as v
c=sqlite3.connect(':memory:')
c.executescript('''
CREATE TABLE arno_experiment_runs(run_id TEXT PRIMARY KEY,case_id INT,root_id TEXT,experiment_family TEXT,treatment TEXT,prompt_blob BLOB,run_metadata_json TEXT,status TEXT);
CREATE TABLE arno_generated_patches(patch_id TEXT PRIMARY KEY,run_id TEXT,content_sha256 TEXT,patch_blob BLOB,patch_uri TEXT,authenticity_status TEXT,notes TEXT);
CREATE TABLE arno_experiment_scans(scan_id TEXT PRIMARY KEY,run_id TEXT,scanner TEXT,scanner_version TEXT,rule_id TEXT,raw_result_blob BLOB,result_json TEXT,execution_verified INTEGER);
CREATE TABLE study_artifacts(artifact_id TEXT PRIMARY KEY,case_id INT,run_id TEXT,role TEXT,source_table TEXT,source_locator TEXT,sha256 TEXT,storage_status TEXT,original_bytes INT);
CREATE TABLE study_runs(run_id TEXT PRIMARY KEY,case_id INT,experimental_family TEXT,treatment TEXT,run_status TEXT,source_snapshot_type TEXT,patch_id TEXT,patch_sha256 TEXT,patch_embedded INT,scan_id TEXT,raw_scan_embedded INT,scan_execution_verified INT,before_count INT,after_count INT,number_new INT,number_new_target INT,before_sarif_sha256 TEXT,after_sarif_sha256 TEXT,historical_revision_equivalence TEXT,functional_status TEXT,patch_provenance_status TEXT,raw_patch_source_table TEXT,raw_scan_source_table TEXT,metrics_source_table TEXT);
''')
v.new_schema(c)
dat={"run":"TEST_RUN", "case":3429, "cohort":"OCT2026_P123_NEW_RETROSPECTIVE",
     "arm":"P2", "source":"FULL_FROZEN_SNAPSHOT", "tree_sha":"a", "source_zip_sha":"b",
     "patch_sha":v.digest(b'patch'),"after_sha":v.digest(b'sarif'),"before_sha":v.digest(b'before'),
     "baseline":1,"after":2,"new":1,"receipt_status":"COMPLETED", "agent_status":"COMPLETED",
     "functional":"NOT_TESTED", "assets":[("PATCH",b"patch","mock_source"),
       ("CODEQL_AFTER_SARIF",b"sarif","mock_source"),
       ("CODEQL_BEFORE_SARIF",b"before","mock_source")]}
assert v.add_run(c,dat)=="newly_imported"
assert c.execute('select count(*) from study_runs').fetchone()[0]==1
assert c.execute('select count(*) from arno_v2_evidence_bytes').fetchone()[0]==3
assert c.execute('select length(patch_blob) from arno_generated_patches').fetchone()[0]==5
assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
print('PASS: mock v2 normalized insertion, 3 raw evidence blobs, SQLite integrity')
