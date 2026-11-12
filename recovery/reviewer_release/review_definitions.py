PURPOSES = {
    'cases': 'Stable case registry linking repository, upstream issue and pull request.',
    'arno_sources': 'Source provenance and optional embedded source bytes; source locators may be historical.',
    'arno_classifications': 'Original 122-case annotations, including first-pass, corrections and final fields.',
    'arno_annotation_events': 'Annotation history by case, dimension and event stage; stages are not timestamps.',
    'arno_frozen_broad_attribution': 'Frozen 455 producing-change attributions; identifiers are cohort-scoped.',
    'arno_canonical_id_pc_links': 'Historical canonical-finding crosswalk; retained pending flags can be stale.',
    'arno_root_decisions': 'Frozen root census; pending coding status must not override recovered final D7 records.',
    'arno_d7_final_roots_342': 'Recovered final 342-root coding; does not establish independent human adjudication.',
    'arno_d7_final_M_roots_233': 'Recovered M-only subset; do not add to the 342-root table as separate observations.',
    'arno_new70_canonical_prelim_254': 'Preliminary candidates; not the final NEW70 finding denominator.',
    'arno_new70_final_findings': 'Recovered final NEW70 finding rows; scanner findings are not confirmed vulnerabilities.',
    'arno_stage_ledger': 'Historical recovery log with concatenated updates; not a current completeness authority.',
    'arno_rq_publication_claim_audit': 'Historical claim audit; consult explicit claim supersession before interpreting gaps.',
    'arno_claim_status_supersession_20261029': 'Explicit claim-level corrections with source evidence and caveats.',
    'arno_experiment_runs': 'Experiment registry; archived originals, later analyses and new generations coexist.',
    'arno_generated_patches': 'Patch bytes and authenticity qualifications linked to experiment runs.',
    'arno_experiment_scans': 'Run-linked scanner outputs; execution verification and functional validity are separate.',
    'arno_chat_evidence_objects': 'Explicit run/case artifact associations, hashes and optional embedded payloads.',
    'arno_owp14_fresh_o_reruns_20261031': 'Two later non-blind generations; explicitly not recovered historical O arms.',
    'arno_rq3_owp14_run_scans': '40 archived O/W/P scanner conditions; two historical O arms are absent.',
    'arno_rq2_c6_reproduced_tests': 'Recorded reproduction of nine statistical tests; human review provenance remains qualified.',
}


def group(name):
    if name.startswith('arno_archive_vault_'):
        return 'embedded_archive', 'Archived payloads and their original metadata; not extra experiments.'
    if name in ('arno_classifications', 'arno_annotation_events') or name.startswith('arno_original_'):
        return 'rq1_original122', 'Original 122-case annotation and source history.'
    if name.startswith('arno_new70_'):
        return 'rq1_new70', 'NEW70 evidence; preliminary, final and historical rows must remain distinguished.'
    if name.startswith(('arno_rq2_', 'arno_matched_control_', 'arno_c6_')):
        return 'rq2_controls_statistics', 'Matched controls and recorded statistical evidence.'
    if name.startswith(('arno_rq3_', 'arno_owp14_', 'arno_screen65_')) or name in ('arno_experiment_runs', 'arno_generated_patches', 'arno_experiment_scans', 'arno_chat_pending_runs'):
        return 'rq3_experiments', 'Experiments and scanner evidence; consult review_v_runs for run origin.'
    if name.startswith(('arno_d7_', 'arno_D_', 'arno_root_', 'arno_pc_', 'arno_choice_', 'arno_mechanism_', 'arno_frozen_', 'arno_canonical_')):
        return 'coding_lineage', 'Producing-change, root and coding lineage.'
    if name.startswith(('arno_chat_', 'arno_evidence_', 'arno_exp_transfer_', 'arno_recovered_', 'arno_patch_fragment_')):
        return 'artifact_provenance', 'Preserved evidence, transport and artifact associations.'
    if name.startswith('arno_'):
        return 'provenance_audit', 'Source/recovery/audit evidence; historical statuses are retained verbatim.'
    return 'mining_baseline', 'Original mining corpus, scanner jobs and operational records.'


SCHEMA = '''
CREATE TABLE review_policy(policy_key TEXT PRIMARY KEY,rule TEXT NOT NULL);
CREATE TABLE review_table_catalog(table_name TEXT PRIMARY KEY,domain TEXT NOT NULL,purpose TEXT NOT NULL,lifecycle TEXT NOT NULL,source_row_count INTEGER NOT NULL,notes TEXT NOT NULL);
CREATE TABLE review_column_catalog(table_name TEXT NOT NULL,column_name TEXT NOT NULL,data_type TEXT,declared_not_null INTEGER,pk_position INTEGER,default_sql TEXT,notes TEXT NOT NULL,PRIMARY KEY(table_name,column_name));
CREATE TABLE review_relationship_catalog(child_table TEXT NOT NULL,foreign_key_id INTEGER NOT NULL,column_sequence INTEGER NOT NULL,child_column TEXT,parent_table TEXT,parent_column TEXT,on_update_action TEXT,on_delete_action TEXT,PRIMARY KEY(child_table,foreign_key_id,column_sequence));
CREATE TABLE review_run_catalog(run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),evidence_class TEXT NOT NULL,selection_policy TEXT NOT NULL,classification_basis TEXT NOT NULL,classification_evidence_json TEXT NOT NULL,functional_validity TEXT NOT NULL,independent_generation_attestation TEXT NOT NULL);
CREATE TABLE review_claim_history(evidence_id TEXT PRIMARY KEY,source_table TEXT NOT NULL,source_key TEXT NOT NULL,claim_key TEXT NOT NULL,rq TEXT,status TEXT,statement TEXT,caveat TEXT,explicit_correction INTEGER NOT NULL);
CREATE TABLE review_quality_issues(issue_id TEXT PRIMARY KEY,severity TEXT NOT NULL,entity_type TEXT NOT NULL,entity_key TEXT NOT NULL,issue TEXT NOT NULL,interpretation TEXT NOT NULL);
CREATE TABLE review_artifact_index(artifact_key TEXT PRIMARY KEY,source_table TEXT NOT NULL,source_pk_json TEXT NOT NULL,case_id INTEGER,run_id TEXT,role TEXT NOT NULL,sha256 TEXT,original_bytes INTEGER,embedded INTEGER NOT NULL,payload_column TEXT,encoding TEXT NOT NULL,source_locator TEXT,association_basis TEXT NOT NULL);
CREATE INDEX review_artifact_case ON review_artifact_index(case_id);
CREATE INDEX review_artifact_run ON review_artifact_index(run_id);
'''


POLICY = {
    'source_preservation': 'All original tables, rows and views are copied unchanged. No historical result is deleted, relabelled or overwritten.',
    'correction_precedence': 'Only an explicit claim_id match in the documented supersession table changes the displayed claim-audit status. A later timestamp alone confers no authority.',
    'experiment_precedence': 'Original archived experiments, historical-patch rescans, baselines and later exploratory generations are separate evidence classes. New runs never fill missing historical arms.',
    'analysis_selection': 'Run classes are navigation labels, not scientific validation. Historical candidates require an explicit analysis protocol; later exploratory runs are supplementary only by default.',
    'independent_review': 'Hash matching establishes byte integrity, not agent origin, human adjudication, functional correctness or causal prevention.',
    'null_prompt': 'A null prompt field means no prompt in that field. It does not establish absence from input packets or archives. Self-written prompts are not automatically complete model invocation traces.',
    'identifier_scope': 'Use case_id for cases, run_id for runs, and cohort plus producing_change_id for producing changes. Preliminary and final canonical IDs must not be merged by bare ID.',
    'denominators': 'Keep raw scanner positives, included cohorts, findings, producing changes, roots and runs distinct. Views expose those units separately.',
    'historical_status': 'Pending flags in old tables and concatenated stage notes are historical evidence, not a current consolidated readiness decision.',
    'privacy': 'This edition retains original research bytes and may include sensitive material. Keep the database private pending a separate disclosure review.',
}


VIEWS = {
    'review_v_cases': '''SELECT c.id AS case_id,c.repo_id,c.issue_id,c.pr_id,c.ai_cohort,c.status AS mining_status,c.final_label AS mining_label,
       EXISTS(SELECT 1 FROM arno_classifications a WHERE a.case_id=c.id) AS in_original122,
       EXISTS(SELECT 1 FROM arno_new70_context_frozen n WHERE n.case_id=c.id) AS in_new70,
       (SELECT COUNT(*) FROM arno_experiment_runs r WHERE r.case_id=c.id) AS experiment_runs FROM cases c''',
    'review_v_original122': 'SELECT * FROM arno_classifications',
    'review_v_annotation_history': 'SELECT * FROM arno_annotation_events',
    'review_v_new70_final_findings': 'SELECT * FROM arno_new70_final_findings',
    'review_v_new70_preliminary_candidates': 'SELECT * FROM arno_new70_canonical_prelim_254',
    'review_v_producing_changes': 'SELECT * FROM arno_frozen_broad_attribution',
    'review_v_final_root_coding': 'SELECT * FROM arno_d7_final_roots_342',
    'review_v_matched_pairs': 'SELECT * FROM arno_matched_control_pairs_C2',
    'review_v_reproduced_statistics': 'SELECT * FROM arno_rq2_c6_reproduced_tests',
    'review_v_runs': '''SELECT r.run_id,r.case_id,r.root_id,r.experiment_family,r.treatment,r.status AS source_status,
       p.evidence_class,p.selection_policy,p.classification_basis,p.functional_validity,p.independent_generation_attestation,
       CASE WHEN r.prompt_blob IS NOT NULL THEN 'MAIN_FIELD_PRESENT' WHEN EXISTS(SELECT 1 FROM arno_chat_evidence_objects e WHERE e.run_id=r.run_id AND e.role='self_written_prompt' AND e.content_zlib IS NOT NULL) THEN 'SELF_WRITTEN_PROMPT_ARTIFACT_PRESENT_INVOCATION_UNVERIFIED' ELSE 'MAIN_FIELD_EMPTY_CHECK_ARCHIVED_INPUT_PACKETS' END AS prompt_status,
       (SELECT COUNT(*) FROM arno_generated_patches g WHERE g.run_id=r.run_id) AS patch_count,
       (SELECT COUNT(*) FROM arno_experiment_scans s WHERE s.run_id=r.run_id) AS scan_count,
       (SELECT COUNT(*) FROM review_artifact_index a WHERE a.run_id=r.run_id) AS indexed_artifact_count
       FROM arno_experiment_runs r JOIN review_run_catalog p USING(run_id)''',
    'review_v_archived_owp_runs': "SELECT * FROM review_v_runs WHERE evidence_class='ARCHIVED_ORIGINAL_OWP'",
    'review_v_later_exploratory_runs': "SELECT * FROM review_v_runs WHERE selection_policy='SUPPLEMENTARY_ONLY'",
    'review_v_patches': '''SELECT p.patch_id,p.run_id,r.case_id,r.evidence_class,p.content_sha256,p.authenticity_status,
       p.patch_blob IS NOT NULL AS embedded,p.patch_uri,p.notes FROM arno_generated_patches p LEFT JOIN review_v_runs r USING(run_id)''',
    'review_v_scans': '''SELECT s.scan_id,s.run_id,r.case_id,r.evidence_class,s.scanner,s.scanner_version,s.rule_id,s.execution_verified,
       s.raw_result_blob IS NOT NULL AS raw_result_embedded,r.functional_validity FROM arno_experiment_scans s LEFT JOIN review_v_runs r USING(run_id)''',
    'review_v_claims_current': '''SELECT a.claim_id,a.rq,a.paper_or_archive_value,a.database_value,a.reproduce_sql,
       a.audit_status AS historical_audit_status,COALESCE(s.current_evidence_status,a.audit_status) AS documented_current_status,
       CASE WHEN s.claim_id IS NOT NULL THEN 'EXPLICIT_CLAIM_ID_SUPERSESSION' ELSE 'HISTORICAL_AUDIT_NO_EXPLICIT_SUPERSESSION' END AS resolution_rule,
       a.caveat AS historical_caveat,COALESCE(s.caveat,a.caveat) AS current_caveat,s.evidence,s.source_key
       FROM arno_rq_publication_claim_audit a LEFT JOIN arno_claim_status_supersession_20261029 s USING(claim_id)
       UNION ALL SELECT s.claim_id,s.rq,NULL,NULL,NULL,NULL,s.current_evidence_status,'EXPLICIT_SUPERSESSION_ADDITIONAL_CLAIM',NULL,s.caveat,s.evidence,s.source_key
       FROM arno_claim_status_supersession_20261029 s LEFT JOIN arno_rq_publication_claim_audit a USING(claim_id) WHERE a.claim_id IS NULL''',
    'review_v_claim_evidence_history': 'SELECT * FROM review_claim_history',
    'review_v_artifacts': 'SELECT * FROM review_artifact_index',
    'review_v_quality_issues': 'SELECT * FROM review_quality_issues',
}

