-- Complete ARNO Wits master SQLite schema; contains DDL only, NOT data.
-- Export: 2026-10-31T10:36:09.756523+00:00
-- Source: /home-mscluster/astrauss/research_artifacts/ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite
-- Opened file in SQLite URI mode=ro with PRAGMA query_only=ON.

BEGIN TRANSACTION;

-- TABLE: ai_markers
CREATE TABLE ai_markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    issue_id INTEGER,
    pr_id INTEGER,
    marker_text TEXT NOT NULL,
    marker_location TEXT NOT NULL,
    confidence TEXT NOT NULL,
    matched_tool TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: arno_D_root_evidence_index
CREATE TABLE arno_D_root_evidence_index (
      root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),
      producing_change_count INTEGER NOT NULL,
      pass_A_evidence_items INTEGER NOT NULL,
      pass_B_evidence_items INTEGER NOT NULL,
      issue_preintro_human_status TEXT,
      true_base_target_status TEXT,bounded_repo_search_status TEXT,
      project_instructions_status TEXT,dependency_toolchain_status TEXT,
      external_guidance_status TEXT,chronology_status TEXT,
      frozen_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
      evidence_kind TEXT NOT NULL DEFAULT 'PRE_ADJUDICATION_EVIDENCE_PACKET'
    );

-- TABLE: arno_annotation_events
CREATE TABLE arno_annotation_events(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 case_id INTEGER NOT NULL REFERENCES arno_classifications(case_id),
 dimension TEXT NOT NULL, event_stage TEXT NOT NULL, label_value TEXT,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
 notes TEXT, UNIQUE(case_id,dimension,event_stage)
);

-- TABLE: arno_archive_vault_chunks
CREATE TABLE arno_archive_vault_chunks(
    object_key TEXT NOT NULL REFERENCES arno_archive_vault_objects(object_key),
    sequence INTEGER NOT NULL,bytes BLOB NOT NULL,content_sha256 TEXT NOT NULL,
    PRIMARY KEY(object_key,sequence)
   );

-- TABLE: arno_archive_vault_members
CREATE TABLE arno_archive_vault_members(
    archive_name TEXT NOT NULL,member_path TEXT NOT NULL,case_id TEXT,
    role TEXT NOT NULL,sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    indexed_in_master INTEGER NOT NULL,matched_master_tables TEXT,
    PRIMARY KEY(archive_name,member_path)
   );

-- TABLE: arno_archive_vault_metadata
CREATE TABLE arno_archive_vault_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

-- TABLE: arno_archive_vault_objects
CREATE TABLE arno_archive_vault_objects(
    object_key TEXT PRIMARY KEY,source_kind TEXT NOT NULL,source_locator TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    segment_count INTEGER NOT NULL,case_id INTEGER,source_key TEXT
   );

-- TABLE: arno_archive_vault_sources
CREATE TABLE arno_archive_vault_sources(
    source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
    kind TEXT NOT NULL,original_locator TEXT NOT NULL,expected_sha256 TEXT,
    vault_object_key TEXT,coverage_status TEXT NOT NULL
   );

-- TABLE: arno_c6_bootstrap_reproduction_artifacts
CREATE TABLE arno_c6_bootstrap_reproduction_artifacts(
   artifact_key TEXT PRIMARY KEY, original_relative_path TEXT NOT NULL,
   sha256 TEXT NOT NULL,content_zlib BLOB NOT NULL,original_bytes INTEGER NOT NULL);

-- TABLE: arno_c6_independent_bootstrap_replication
CREATE TABLE arno_c6_independent_bootstrap_replication(
  variable TEXT PRIMARY KEY, effect TEXT NOT NULL, original_point_estimate REAL NOT NULL,
  independent_point_estimate REAL NOT NULL, original_ci_low REAL NOT NULL,
  original_ci_high REAL NOT NULL, independent_ci_low REAL NOT NULL,independent_ci_high REAL NOT NULL,
  lower_bound_abs_difference REAL NOT NULL,upper_bound_abs_difference REAL NOT NULL,
  frozen_num_repo_blocks INTEGER NOT NULL,largest_block INTEGER NOT NULL,
  seed INTEGER NOT NULL,bootstrap_replicates INTEGER NOT NULL,
  evidence_status TEXT NOT NULL,run_utc TEXT NOT NULL);

-- TABLE: arno_canonical_id_pc_links
CREATE TABLE arno_canonical_id_pc_links(
  canonical_finding_id TEXT PRIMARY KEY,
  cohort TEXT NOT NULL,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL REFERENCES arno_mechanism_selection(decision_id),
  root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
  source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
  detailed_step1_import_status TEXT NOT NULL CHECK(detailed_step1_import_status IN ('PENDING_ORIGINAL_SHEET','PENDING_NEW70_FINAL_SHEET')),
  FOREIGN KEY(cohort,producing_change_id) REFERENCES arno_frozen_broad_attribution(cohort,producing_change_id));

-- TABLE: arno_chat_codeql_findings
CREATE TABLE arno_chat_codeql_findings(
 finding_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 result_index INTEGER NOT NULL,rule_id TEXT NOT NULL,file_path TEXT NOT NULL,
 line INTEGER,column INTEGER,level TEXT,message TEXT NOT NULL,
 signature_sha256 TEXT NOT NULL,
 new_vs_baseline INTEGER NOT NULL CHECK(new_vs_baseline IN(0,1)),
 matches_historical_p1 INTEGER NOT NULL CHECK(matches_historical_p1 IN(0,1)),
 raw_result_json TEXT NOT NULL,
 UNIQUE(run_id,result_index));

-- TABLE: arno_chat_codeql_metrics
CREATE TABLE arno_chat_codeql_metrics (
 run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 case_label TEXT NOT NULL, method TEXT NOT NULL,
 source_kind TEXT NOT NULL, source_tree_sha256 TEXT NOT NULL, source_zip_sha256 TEXT NOT NULL,
 baseline_total INTEGER NOT NULL, after_total INTEGER NOT NULL,
 new_vs_baseline INTEGER NOT NULL, historical_p1_new INTEGER NOT NULL,
 historical_p1_remaining INTEGER,
 codeql_version TEXT NOT NULL, codeql_suite TEXT NOT NULL, sarif_sha256 TEXT NOT NULL,
 patch_sha256 TEXT, receipt_status TEXT NOT NULL, functional_status TEXT NOT NULL,
 provenance_status TEXT NOT NULL, result_metadata_json TEXT NOT NULL);

-- TABLE: arno_chat_evidence_objects
CREATE TABLE arno_chat_evidence_objects(
 artifact_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 role TEXT NOT NULL, source_locator TEXT NOT NULL,
 sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL,
 compression TEXT NOT NULL,content_zlib BLOB,verification_status TEXT NOT NULL,
 UNIQUE(run_id,role,sha256));

-- TABLE: arno_chat_ingest_ledger
CREATE TABLE arno_chat_ingest_ledger(
 batch_id TEXT PRIMARY KEY,ingested_utc TEXT NOT NULL,
 source_manifest_sha256 TEXT NOT NULL,completed_runs INTEGER NOT NULL,
 patch_count INTEGER NOT NULL,sarif_count INTEGER NOT NULL,
 finding_count INTEGER NOT NULL,missing_receipts_json TEXT NOT NULL,
 preexisting_counts_json TEXT NOT NULL,notes TEXT);

-- TABLE: arno_chat_pending_runs
CREATE TABLE arno_chat_pending_runs(
 run_id TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 method TEXT NOT NULL,status TEXT NOT NULL,agent_input_basename TEXT,
 missing_artifacts_json TEXT NOT NULL,notes TEXT);

-- TABLE: arno_choice_case_split
CREATE TABLE arno_choice_case_split(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),partition TEXT NOT NULL,
 rank INTEGER UNIQUE NOT NULL,selection_hash TEXT UNIQUE NOT NULL,
 pc_count INTEGER NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_choice_eligible_pc
CREATE TABLE arno_choice_eligible_pc(
 pc_id TEXT PRIMARY KEY REFERENCES arno_mechanism_selection(decision_id),
 case_id INTEGER NOT NULL REFERENCES arno_choice_case_split(case_id),
 partition TEXT NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_claim_status_supersession_20261029
CREATE TABLE arno_claim_status_supersession_20261029 (claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,current_evidence_status TEXT NOT NULL,evidence TEXT NOT NULL,caveat TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_classifications
CREATE TABLE arno_classifications(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id), review_number INTEGER UNIQUE NOT NULL,
 issue_request_summary TEXT, issue_purpose TEXT, instruction_specificity TEXT, request_scope TEXT,
 pr_stated_goal_summary TEXT, pr_purpose TEXT, goal_alignment TEXT,
 implementation_summary TEXT, implementation_first_pass TEXT, implementation_correction TEXT, implementation_final TEXT,
 risk_first_pass TEXT, risk_correction TEXT, risk_final TEXT, risk_human_review TEXT,
 agent_tool TEXT, agent_provenance TEXT,
 original_row_json TEXT NOT NULL, imported_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
 raw_row_sha256 TEXT NOT NULL
);

-- TABLE: arno_codeql_oct19_original_archive_inventory
CREATE TABLE arno_codeql_oct19_original_archive_inventory (
    source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
    file_name TEXT NOT NULL UNIQUE,relative_path TEXT NOT NULL UNIQUE,
    original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    member_count INTEGER,handling TEXT NOT NULL,
    original_manifest_source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
  );

-- TABLE: arno_cohort_membership
CREATE TABLE arno_cohort_membership(
        case_id INTEGER NOT NULL REFERENCES cases(id),
        cohort_key TEXT NOT NULL, membership_label TEXT NOT NULL,
        source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
        PRIMARY KEY(case_id,cohort_key)
    );

-- TABLE: arno_d7_final_M_roots_233
CREATE TABLE arno_d7_final_M_roots_233(
    root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
    case_id INTEGER NOT NULL REFERENCES cases(id),
    final_route TEXT NOT NULL CHECK(final_route='M'),
    final_tier TEXT NOT NULL,
    d7_cohort TEXT NOT NULL,
    pass_a_route TEXT,pass_b_route TEXT,
    mandatory_d4 TEXT,d4_reasons TEXT,
    final_evidence_complete TEXT,final_chronology_ok TEXT,
    final_route_confidence TEXT,final_explanation_confidence TEXT,
    adjudication_rationale TEXT NOT NULL,
    original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    final_adjudication_status TEXT NOT NULL DEFAULT 'FINAL_D7_M_SUBSET'
 );

-- TABLE: arno_d7_final_roots_342
CREATE TABLE arno_d7_final_roots_342 (
      root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),repository TEXT NOT NULL,
      pc_count INTEGER NOT NULL,final_route TEXT NOT NULL CHECK(final_route IN ('M','H','T')),
      final_tier TEXT NOT NULL,d7_cohort TEXT NOT NULL,final_route_confidence TEXT NOT NULL,
      final_explanation_confidence TEXT,chronology_status TEXT NOT NULL,
      evidence_complete TEXT NOT NULL,evidence_ids TEXT,
      adjudication_rationale TEXT NOT NULL,original_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_evidence_assets
CREATE TABLE arno_evidence_assets(source_path TEXT PRIMARY KEY, cohort TEXT NOT NULL, artifact_role TEXT NOT NULL, source_sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL, content_zlib BLOB NOT NULL, verification TEXT NOT NULL);

-- TABLE: arno_excluded_cases
CREATE TABLE arno_excluded_cases(
        case_id INTEGER PRIMARY KEY REFERENCES cases(id),
        repository TEXT, pr_number INTEGER, validation_type TEXT,
        historical_verdict TEXT NOT NULL, old_finding_count INTEGER,
        corrected_finding_count INTEGER, exclusion_reason TEXT NOT NULL,
        original_row_json TEXT NOT NULL, source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
    );

-- TABLE: arno_exp_transfer_files
CREATE TABLE arno_exp_transfer_files(
    source_path TEXT PRIMARY KEY,
    source_group TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    original_byte_count INTEGER NOT NULL,
    original_zlib BLOB NOT NULL,
    provenance_status TEXT NOT NULL DEFAULT 'ORIGINAL_UPLOAD_VERIFIED'
 );

-- TABLE: arno_experiment_runs
CREATE TABLE arno_experiment_runs(
 run_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 root_id TEXT REFERENCES arno_root_decisions(root_id), experiment_family TEXT NOT NULL,
 treatment TEXT, prompt_blob BLOB, run_metadata_json TEXT, status TEXT NOT NULL
);

-- TABLE: arno_experiment_scans
CREATE TABLE arno_experiment_scans(
 scan_id TEXT PRIMARY KEY, run_id TEXT REFERENCES arno_experiment_runs(run_id),
 scanner TEXT NOT NULL, scanner_version TEXT, rule_id TEXT,
 raw_result_blob BLOB, result_json TEXT, execution_verified INTEGER NOT NULL DEFAULT 0
);

-- TABLE: arno_frozen_broad_attribution
CREATE TABLE arno_frozen_broad_attribution(
  cohort TEXT NOT NULL CHECK(cohort IN('original122','new70')),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL UNIQUE REFERENCES arno_mechanism_selection(decision_id),
  case_id INTEGER NOT NULL REFERENCES cases(id),
  root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
  attribution TEXT NOT NULL,
  attribution_basis TEXT,
  attribution_reason TEXT,
  source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
  provenance_kind TEXT NOT NULL,
  PRIMARY KEY(cohort,producing_change_id));

-- TABLE: arno_generated_patches
CREATE TABLE arno_generated_patches(
 patch_id TEXT PRIMARY KEY, run_id TEXT REFERENCES arno_experiment_runs(run_id),
 content_sha256 TEXT, patch_blob BLOB, patch_uri TEXT, authenticity_status TEXT NOT NULL,
 notes TEXT
);

-- TABLE: arno_matched_control_C1_opportunity
CREATE TABLE arno_matched_control_C1_opportunity(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    is_positive INTEGER NOT NULL CHECK(is_positive IN(0,1)),
    scanner_opportunity_signature TEXT,
    source_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_matched_control_C3_blind_inputs
CREATE TABLE arno_matched_control_C3_blind_inputs(
    blind_id TEXT PRIMARY KEY,
    positive_case_id INTEGER NOT NULL REFERENCES arno_matched_control_pairs_C2(positive_case_id),
    control_case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
    issue_blind_json TEXT NOT NULL,
    pr_blind_json TEXT NOT NULL,
    context_raw_json TEXT NOT NULL,
    blinded_manifest_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_matched_control_C3_impl_packets
CREATE TABLE arno_matched_control_C3_impl_packets(
    blind_id TEXT NOT NULL REFERENCES arno_matched_control_C3_blind_inputs(blind_id),
    packet_kind TEXT NOT NULL CHECK(packet_kind IN('raw','blind')),
    original_sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    compressed_bytes BLOB NOT NULL,
    source_path TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(blind_id,packet_kind));

-- TABLE: arno_matched_control_pairs_C2
CREATE TABLE arno_matched_control_pairs_C2(
    positive_case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    control_case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
    blind_id TEXT NOT NULL UNIQUE,
    match_tier TEXT NOT NULL,
    same_repository INTEGER NOT NULL CHECK(same_repository IN(0,1)),
    positive_repository TEXT,control_repository TEXT,
    opportunity_relation TEXT,
    normalized_distance REAL,
    original_C2_row_json TEXT NOT NULL,
    original_C3_locked_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    provenance_kind TEXT NOT NULL DEFAULT 'C2_MATCHED_CONTROL_NOT_OUTCOME');

-- TABLE: arno_matched_control_unmatched_C2
CREATE TABLE arno_matched_control_unmatched_C2(
    positive_case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    reason TEXT NOT NULL,original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key));

-- TABLE: arno_mechanism_selection
CREATE TABLE arno_mechanism_selection(
 decision_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 producing_change_id TEXT, choice_summary TEXT, evidence_json TEXT,
 evidence_source_key TEXT REFERENCES arno_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);

-- TABLE: arno_new70_canonical_prelim_254
CREATE TABLE arno_new70_canonical_prelim_254(
    preliminary_finding_id TEXT PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    qc_status TEXT,
    finding_family TEXT, rule_id TEXT, canonical_finding TEXT,
    scanner TEXT, raw_scanner_row_count INTEGER,
    original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    freeze_status TEXT NOT NULL DEFAULT 'PRE_QC_NOT_FINAL'
 );

-- TABLE: arno_new70_context_frozen
CREATE TABLE arno_new70_context_frozen(
   case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
   review_number INTEGER NOT NULL,issue_author TEXT,
   author_association TEXT,human_review_before_merge TEXT,
   original_context_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 );

-- TABLE: arno_new70_final_finding_maps
CREATE TABLE arno_new70_final_finding_maps (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, mapping_status TEXT NOT NULL CHECK(mapping_status IN ('Mapped','Not isolated')),
 producing_change_id TEXT REFERENCES arno_new70_final_producing_changes(producing_change_id),
 mapping_basis TEXT, changed_locations TEXT, diff_evidence TEXT,
 frozen_source_raw_ids TEXT NOT NULL, no_mapping_reason TEXT,
 attribution_status TEXT NOT NULL,
 original_row_json TEXT NOT NULL,
 CHECK((mapping_status='Mapped' AND producing_change_id IS NOT NULL) OR (mapping_status='Not isolated' AND producing_change_id IS NULL)));

-- TABLE: arno_new70_final_findings
CREATE TABLE arno_new70_final_findings (
 canonical_finding_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, repository TEXT NOT NULL,
 pr_number TEXT NOT NULL, finding_family TEXT NOT NULL, scanner TEXT NOT NULL,
 rule_id TEXT, description TEXT NOT NULL, primary_file TEXT, severity TEXT,
 raw_scanner_row_count INTEGER NOT NULL, frozen_qc_status TEXT NOT NULL,
 reviewer_identity_status TEXT NOT NULL,
 original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_final_freeze_manifest
CREATE TABLE arno_new70_final_freeze_manifest (
 metric TEXT PRIMARY KEY, stored_value TEXT NOT NULL, verification_status TEXT NOT NULL, explanation TEXT);

-- TABLE: arno_new70_final_method_qc
CREATE TABLE arno_new70_final_method_qc (
 record_key TEXT PRIMARY KEY, stage TEXT NOT NULL, metric TEXT, reported_status TEXT,
 original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_final_producing_changes
CREATE TABLE arno_new70_final_producing_changes (
 producing_change_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, repository TEXT NOT NULL,
 pr_number TEXT NOT NULL, change_description TEXT NOT NULL, mapping_bases TEXT NOT NULL,
 changed_locations TEXT NOT NULL, pr_diff_evidence TEXT NOT NULL,
 pr_diff_source TEXT NOT NULL, canonical_finding_count INTEGER NOT NULL,
 original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_final_publication_status
CREATE TABLE arno_new70_final_publication_status (
    claim_key TEXT PRIMARY KEY,rq TEXT NOT NULL,verification TEXT NOT NULL,
    claim_text TEXT NOT NULL,source_table TEXT NOT NULL,qualifications TEXT NOT NULL,
    replaces_prior_missing_artifact_flag INTEGER NOT NULL);

-- TABLE: arno_new70_final_raw_finding_links
CREATE TABLE arno_new70_final_raw_finding_links (
 raw_finding_id TEXT PRIMARY KEY, canonical_finding_id TEXT NOT NULL REFERENCES arno_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, scanner TEXT NOT NULL, finding_rule TEXT,
 original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_final_source_blobs
CREATE TABLE arno_new70_final_source_blobs (
 source_key TEXT PRIMARY KEY, original_name TEXT NOT NULL, container TEXT NOT NULL,
 byte_size INTEGER NOT NULL, sha256 TEXT NOT NULL, content_zlib BLOB NOT NULL,
 evidence_state TEXT NOT NULL);

-- TABLE: arno_new70_final_source_id_audit
CREATE TABLE arno_new70_final_source_id_audit (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_new70_final_findings(canonical_finding_id),
 original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_final_unresolved
CREATE TABLE arno_new70_final_unresolved (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, explanation TEXT NOT NULL, original_row_json TEXT NOT NULL);

-- TABLE: arno_new70_id_version_conflicts
CREATE TABLE arno_new70_id_version_conflicts(
    preliminary_finding_id TEXT PRIMARY KEY REFERENCES arno_new70_canonical_prelim_254(preliminary_finding_id),
    preliminary_case_id INTEGER NOT NULL REFERENCES cases(id),
    later_provenance_case_id INTEGER NOT NULL REFERENCES cases(id),
    id_collision_status TEXT NOT NULL,
    audit_source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 );

-- TABLE: arno_new70_phase8_synthesis
CREATE TABLE arno_new70_phase8_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
              repository TEXT,case_evidence_summary TEXT,producing_change_profile TEXT,
              qc_status TEXT,qc_note TEXT,frozen_synthesis_input_sha256 TEXT,
              full_original_row_json TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_new70_phase9_full_source
CREATE TABLE arno_new70_phase9_full_source (
              case_id INTEGER PRIMARY KEY REFERENCES arno_new70_phase9_risk(case_id),
              complete_original_row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_new70_phase9_risk
CREATE TABLE arno_new70_phase9_risk(
   case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
   first_pass_risk_label TEXT NOT NULL,
   first_pass_rationale TEXT NOT NULL,
   qc_correction TEXT,
   qc_note TEXT,
   final_risk_label TEXT NOT NULL,
   final_risk_rationale TEXT NOT NULL,
   evidence_channels_considered TEXT,
   remaining_uncertainty TEXT,
   human_review_correction TEXT,
   original_row_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   label_kind TEXT NOT NULL DEFAULT 'PROVISIONAL_ORIGINAL_PHASE9'
 );

-- TABLE: arno_new70_phase9_risk_events
CREATE TABLE arno_new70_phase9_risk_events(
    case_id INTEGER NOT NULL REFERENCES arno_new70_phase9_risk(case_id),
    event_stage TEXT NOT NULL CHECK(event_stage IN ('first_pass','qc_correction','final')),
    label TEXT NOT NULL,notes TEXT,source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(case_id,event_stage));

-- TABLE: arno_new70_scanner_raw_frozen
CREATE TABLE arno_new70_scanner_raw_frozen(
   raw_finding_id INTEGER PRIMARY KEY,
   case_id INTEGER NOT NULL REFERENCES arno_new70_source_inputs(case_id),
   pr_id INTEGER NOT NULL,scanner TEXT NOT NULL,
   finding_type TEXT,severity TEXT,rule_id TEXT,cwe TEXT,
   file_path TEXT,line_number INTEGER,description TEXT,evidence TEXT,
   raw_json TEXT,introduced INTEGER NOT NULL CHECK(introduced IN(0,1)),
   created_at TEXT,original_row_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   evidence_stage TEXT NOT NULL DEFAULT 'RAW_FROZEN_NOT_FINAL');

-- TABLE: arno_new70_source_inputs
CREATE TABLE arno_new70_source_inputs(
   case_id INTEGER PRIMARY KEY REFERENCES cases(id),
   pr_id INTEGER NOT NULL REFERENCES pull_requests(id),
   review_number INTEGER NOT NULL UNIQUE,
   issue_title TEXT,issue_body TEXT,pr_title TEXT,pr_body TEXT,
   case_mapping_json TEXT NOT NULL,blind_issue_json TEXT NOT NULL,
   blind_pr_json TEXT NOT NULL,stage4b_index_json TEXT NOT NULL,
   evidence_filename TEXT,evidence_completeness TEXT,
   raw_promoted_flag INTEGER NOT NULL CHECK(raw_promoted_flag IN(0,1)),
   classification_status TEXT NOT NULL DEFAULT 'SOURCE_ONLY',
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 );

-- TABLE: arno_original_case_synthesis
CREATE TABLE arno_original_case_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES arno_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_original_full_risk_source
CREATE TABLE arno_original_full_risk_source (
              case_id INTEGER PRIMARY KEY REFERENCES arno_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_original_step1_detail
CREATE TABLE arno_original_step1_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_canonical_id_pc_links(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),rule_id TEXT,severity TEXT,scanner TEXT,
              finding_description TEXT,row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_original_step2_detail
CREATE TABLE arno_original_step2_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_original_step1_detail(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),source_producing_change_id TEXT NOT NULL,
              mapping_status TEXT,changed_locations TEXT,diff_evidence TEXT,
              row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_original_step3_detail
CREATE TABLE arno_original_step3_detail (
              source_producing_change_id TEXT PRIMARY KEY,
              case_id INTEGER NOT NULL REFERENCES cases(id),first_pass_attribution TEXT,
              first_pass_basis TEXT,qc_correction TEXT,final_attribution TEXT NOT NULL,
              attribution_basis TEXT,attribution_reason TEXT,row_json TEXT NOT NULL,
              original_row_number INTEGER NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );

-- TABLE: arno_owp14_exact_scan_baseline_links_20261029
CREATE TABLE arno_owp14_exact_scan_baseline_links_20261029 (
    case_id INTEGER NOT NULL,arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    baseline_sarif_sha256 TEXT NOT NULL,original_input_packet_sha256 TEXT NOT NULL,
    screen65_first_before_member_path TEXT NOT NULL,
    codeql_version TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,
    exact_match_status TEXT NOT NULL DEFAULT 'BYTE_IDENTICAL_FIRST_WAVE_SARIF_AND_PACKET_SHA',
    historical_pr_revision_equivalence TEXT NOT NULL DEFAULT 'NOT_VERIFIED',
    original_report_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES arno_rq3_owp14_run_scans(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES arno_owp14_original_input_packet_inventory_20261029(case_id,arm),
    FOREIGN KEY(case_id) REFERENCES cases(id)
  );

-- TABLE: arno_owp14_fresh_o_reruns_20261031
CREATE TABLE arno_owp14_fresh_o_reruns_20261031(
 run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 frozen_packet_sha256 TEXT NOT NULL,
 patch_sha256 TEXT NOT NULL,
 after_sarif_sha256 TEXT NOT NULL,
 before_sarif_sha256 TEXT NOT NULL,
 historical_O_recovered INTEGER NOT NULL CHECK(historical_O_recovered=0),
 contributes_to_original_triple_count INTEGER NOT NULL CHECK(contributes_to_original_triple_count=0),
 source_model TEXT NOT NULL,
 provenance_status TEXT NOT NULL,
 functional_status TEXT NOT NULL,
 generation_date TEXT NOT NULL
 );

-- TABLE: arno_owp14_input_repo_equivalence_20261029
CREATE TABLE arno_owp14_input_repo_equivalence_20261029 (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    repo_tree_sha256 TEXT NOT NULL,repo_member_count INTEGER NOT NULL,
    repo_total_bytes INTEGER NOT NULL,source_packet_arms INTEGER NOT NULL,
    distinct_issue_md_hashes INTEGER NOT NULL,
    input_equivalence_status TEXT NOT NULL,
    historical_pr_revision_status TEXT NOT NULL,
    historical_issue_wording_status TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
  );

-- TABLE: arno_owp14_original_input_packet_inventory_20261029
CREATE TABLE arno_owp14_original_input_packet_inventory_20261029 (
    case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    original_filename TEXT NOT NULL UNIQUE,original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,historical_issue_text_verified INTEGER NOT NULL,
    baseline_has_historical_rule INTEGER NOT NULL,historical_target_rule TEXT,
    has_exact_original_scan_result_link INTEGER NOT NULL CHECK(has_exact_original_scan_result_link IN (0,1)),
    packet_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    packet_index_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),PRIMARY KEY(case_id,arm));

-- TABLE: arno_patch_fragment_lineage
CREATE TABLE arno_patch_fragment_lineage(
    patch_key TEXT NOT NULL REFERENCES arno_recovered_agent_patch_bytes(patch_key),
    source_path TEXT NOT NULL REFERENCES arno_exp_transfer_files(source_path),
    sequence_number INTEGER NOT NULL,
    PRIMARY KEY(patch_key,source_path)
 );

-- TABLE: arno_pc_root_lineage
CREATE TABLE arno_pc_root_lineage(
       producing_change_id TEXT PRIMARY KEY,
       case_id INTEGER NOT NULL REFERENCES cases(id),
       root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
       original_c5_row_json TEXT NOT NULL,
       source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
    );

-- TABLE: arno_peerreview_recovery_audit_v6_20261028
CREATE TABLE arno_peerreview_recovery_audit_v6_20261028(
  evidence_key TEXT PRIMARY KEY,rq TEXT NOT NULL,status TEXT NOT NULL,
  source_locator TEXT NOT NULL,verified_fact TEXT NOT NULL,
  limitation TEXT NOT NULL,audited_at_utc TEXT NOT NULL);

-- TABLE: arno_postmerge_publication_readiness_20261028
CREATE TABLE arno_postmerge_publication_readiness_20261028(
   audit_key TEXT PRIMARY KEY,rq TEXT NOT NULL,evidence_status TEXT NOT NULL,
   quantitative_summary TEXT NOT NULL,original_evidence_locator TEXT NOT NULL,
   publication_qualification TEXT NOT NULL,verified_at_utc TEXT NOT NULL);

-- TABLE: arno_publication_evidence_status
CREATE TABLE arno_publication_evidence_status(claim_key TEXT PRIMARY KEY, rq TEXT NOT NULL, source_asset TEXT NOT NULL REFERENCES arno_evidence_assets(source_path), status TEXT NOT NULL, limitations TEXT NOT NULL);

-- TABLE: arno_recovered_agent_patch_bytes
CREATE TABLE arno_recovered_agent_patch_bytes(
    patch_key TEXT PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    experimental_condition TEXT NOT NULL,
    replicate_token TEXT NOT NULL,
    origin_kind TEXT NOT NULL,
    original_provenance_json TEXT NOT NULL,
    patch_sha256 TEXT NOT NULL,
    original_byte_count INTEGER NOT NULL,
    patch_zlib BLOB NOT NULL,
    git_unified_diff_header INTEGER NOT NULL CHECK(git_unified_diff_header IN (0,1)),
    patch_execution_status TEXT NOT NULL DEFAULT 'NOT_VERIFIED',
    patch_scanner_status TEXT NOT NULL DEFAULT 'NOT_IMPORTED',
    recovered_at_utc TEXT NOT NULL
 );

-- TABLE: arno_recovery_claim_events_20261028
CREATE TABLE arno_recovery_claim_events_20261028(
   claim_key TEXT PRIMARY KEY, evidence_status TEXT NOT NULL, precise_claim TEXT NOT NULL,
   source_locator TEXT NOT NULL, qualification TEXT NOT NULL, audited_at_utc TEXT NOT NULL);

-- TABLE: arno_recovery_v05_sources
CREATE TABLE arno_recovery_v05_sources (
              source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
              capsule_original_key TEXT NOT NULL, originating_member TEXT NOT NULL,
              original_bytes_size INTEGER NOT NULL,
              original_sha256 TEXT NOT NULL
            );

-- TABLE: arno_root_decisions
CREATE TABLE arno_root_decisions(
 root_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 mechanism_decision_id TEXT REFERENCES arno_mechanism_selection(decision_id),
 producing_change_ids_json TEXT, root_coding_json TEXT,
 evidence_source_key TEXT REFERENCES arno_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);

-- TABLE: arno_rq2_c5_controls
CREATE TABLE arno_rq2_c5_controls(blind_id TEXT PRIMARY KEY, repository TEXT, issue_number TEXT, pr_number TEXT, issue_purpose TEXT, instruction_specificity TEXT, pr_purpose TEXT, goal_alignment TEXT, implementation_pattern TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES arno_evidence_assets(source_path), review_status TEXT NOT NULL);

-- TABLE: arno_rq2_c5_corrections
CREATE TABLE arno_rq2_c5_corrections(blind_id TEXT PRIMARY KEY REFERENCES arno_rq2_c5_controls(blind_id), priority TEXT, corrected_fields TEXT, reason TEXT, original_row_json TEXT NOT NULL, human_verified INTEGER NOT NULL DEFAULT 0, review_provenance TEXT NOT NULL);

-- TABLE: arno_rq2_c5_stability
CREATE TABLE arno_rq2_c5_stability(dimension TEXT PRIMARY KEY, original_row_json TEXT NOT NULL, interpretation TEXT NOT NULL);

-- TABLE: arno_rq2_c6_contingency
CREATE TABLE arno_rq2_c6_contingency(scope TEXT NOT NULL, variable TEXT NOT NULL, positive_category TEXT NOT NULL, control_category TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY(scope,variable,positive_category,control_category));

-- TABLE: arno_rq2_c6_omnibus
CREATE TABLE arno_rq2_c6_omnibus(variable TEXT PRIMARY KEY, n_pairs INTEGER, test TEXT, test_statistic REAL, reported_p REAL, original_row_json TEXT NOT NULL, reproducibility_status TEXT NOT NULL);

-- TABLE: arno_rq2_c6_pairs
CREATE TABLE arno_rq2_c6_pairs(pair_index INTEGER PRIMARY KEY, positive_case_id INTEGER NOT NULL UNIQUE, control_case_id INTEGER NOT NULL UNIQUE, control_blind_id TEXT NOT NULL UNIQUE REFERENCES arno_rq2_c5_controls(blind_id), match_tier TEXT, positive_repository TEXT, control_repository TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES arno_evidence_assets(source_path));

-- TABLE: arno_rq2_c6_reproduced_tests
CREATE TABLE arno_rq2_c6_reproduced_tests(variable TEXT PRIMARY KEY REFERENCES arno_rq2_c6_omnibus(variable), test_family TEXT NOT NULL, n_pairs INTEGER NOT NULL, calculated_p REAL NOT NULL, frozen_p REAL NOT NULL, tolerance_status TEXT NOT NULL, reproduction_record_json TEXT NOT NULL, verification_code_source_path TEXT NOT NULL REFERENCES arno_evidence_assets(source_path));

-- TABLE: arno_rq2_c7_pathways
CREATE TABLE arno_rq2_c7_pathways(pair_index INTEGER PRIMARY KEY REFERENCES arno_rq2_c6_pairs(pair_index), positive_case_id INTEGER NOT NULL, control_case_id INTEGER NOT NULL, positive_broad_pathway TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES arno_evidence_assets(source_path));

-- TABLE: arno_rq3_codeql_screen65_original
CREATE TABLE arno_rq3_codeql_screen65_original(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),source_snapshot_type TEXT NOT NULL,
    generator_claim TEXT,scan_state TEXT NOT NULL,scanner_suite TEXT NOT NULL,
    before_total INTEGER,after_total INTEGER,new_strong INTEGER,new_weak INTEGER,
    historical_target_rules TEXT,new_rule_summary TEXT,
    summary_csv_sha256 TEXT NOT NULL,original_summary_row_json TEXT NOT NULL,
    result_source_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,result_zlib BLOB NOT NULL,
    link_to_generated_patch_status TEXT NOT NULL, functional_status TEXT NOT NULL);

-- TABLE: arno_rq3_owp14_original_artifacts
CREATE TABLE arno_rq3_owp14_original_artifacts(
      source_path TEXT PRIMARY KEY,case_id INTEGER,arm TEXT,
      source_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
      source_zlib BLOB NOT NULL,source_role TEXT NOT NULL);

-- TABLE: arno_rq3_owp14_original_transport
CREATE TABLE arno_rq3_owp14_original_transport(
    source_path TEXT PRIMARY KEY,condition_name TEXT NOT NULL,
    part_number INTEGER NOT NULL,sha256 TEXT NOT NULL,
    raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,status TEXT NOT NULL);

-- TABLE: arno_rq3_owp14_reproduction_checks
CREATE TABLE arno_rq3_owp14_reproduction_checks(
      claim_key TEXT PRIMARY KEY,expected TEXT NOT NULL,observed TEXT NOT NULL,
      status TEXT NOT NULL,qualification TEXT NOT NULL);

-- TABLE: arno_rq3_owp14_run_scans
CREATE TABLE arno_rq3_owp14_run_scans(
      case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
      scan_state TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,codeql_version TEXT NOT NULL,
      historical_target_rule TEXT,new_strong_count INTEGER NOT NULL,new_conservative_count INTEGER NOT NULL,
      target_new_strong INTEGER NOT NULL,patch_sha256 TEXT NOT NULL,
      functional_status TEXT NOT NULL,baseline_codeql_version_match INTEGER,
      original_result_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,original_result_zlib BLOB NOT NULL,
      frozen_summary_row_json TEXT NOT NULL,patch_bytes_match_status TEXT NOT NULL,
      PRIMARY KEY(case_id,arm));

-- TABLE: arno_rq3_owp14_verified_archive
CREATE TABLE arno_rq3_owp14_verified_archive(
     arm TEXT PRIMARY KEY CHECK(arm IN ('O','W','P')),original_zip_sha256 TEXT NOT NULL,
     source_fragment_paths_json TEXT NOT NULL,original_zip_bytes INTEGER NOT NULL,
     zip_zlib BLOB NOT NULL,verification_status TEXT NOT NULL);

-- TABLE: arno_rq3_owp14_verified_patch_bytes
CREATE TABLE arno_rq3_owp14_verified_patch_bytes(
     case_id INTEGER NOT NULL,arm TEXT NOT NULL,original_filename TEXT NOT NULL,
     patch_sha256 TEXT NOT NULL,original_patch_bytes INTEGER NOT NULL,patch_zlib BLOB NOT NULL,
     patch_header_present INTEGER NOT NULL,verification_status TEXT NOT NULL,
     PRIMARY KEY(case_id,arm),
     FOREIGN KEY(case_id,arm) REFERENCES arno_rq3_owp14_run_scans(case_id,arm),
     FOREIGN KEY(arm) REFERENCES arno_rq3_owp14_verified_archive(arm));

-- TABLE: arno_rq3_t1_blind_pairs
CREATE TABLE arno_rq3_t1_blind_pairs(pair_id TEXT PRIMARY KEY, blind_pair_decision TEXT NOT NULL, original_row_json TEXT NOT NULL, human_verified INTEGER NOT NULL DEFAULT 0);

-- TABLE: arno_rq3_t1_blind_sides
CREATE TABLE arno_rq3_t1_blind_sides(pair_id TEXT NOT NULL REFERENCES arno_rq3_t1_blind_pairs(pair_id), blind_side TEXT NOT NULL, original_row_json TEXT NOT NULL, PRIMARY KEY(pair_id,blind_side));

-- TABLE: arno_rq_methodology_sources
CREATE TABLE arno_rq_methodology_sources(
    source_path TEXT PRIMARY KEY, rq TEXT NOT NULL, role TEXT NOT NULL,
    sha256 TEXT NOT NULL,raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,
    integrity_status TEXT NOT NULL,human_verification TEXT NOT NULL);

-- TABLE: arno_rq_publication_claim_audit
CREATE TABLE arno_rq_publication_claim_audit(
    claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,
    paper_or_archive_value TEXT NOT NULL,database_value TEXT,
    reproduce_sql TEXT,audit_status TEXT NOT NULL,
    caveat TEXT NOT NULL,audit_utc TEXT NOT NULL);

-- TABLE: arno_screen65_before_sarif_candidates_20261029
CREATE TABLE arno_screen65_before_sarif_candidates_20261029 (
   case_id INTEGER NOT NULL REFERENCES cases(id),wave TEXT NOT NULL,zip_member_path TEXT NOT NULL UNIQUE,
   original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,sarif_version TEXT NOT NULL,
   tool_versions_json TEXT NOT NULL,scanner_run_count INTEGER NOT NULL,result_count INTEGER NOT NULL,
   comparability_status TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   PRIMARY KEY(case_id,wave));

-- TABLE: arno_screen65_original_results_index
CREATE TABLE arno_screen65_original_results_index(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    patch_key TEXT NOT NULL UNIQUE REFERENCES arno_recovered_agent_patch_bytes(patch_key),
    source_status TEXT,source_notes TEXT,source_filename TEXT NOT NULL,
    original_row_json TEXT NOT NULL,
    provenance_scope TEXT NOT NULL DEFAULT 'UNVERIFIED_EXPERIMENT_INDEX_NOT_A_SCANNER_RESULT'
 );

-- TABLE: arno_seven_final_repair_archive
CREATE TABLE arno_seven_final_repair_archive(
      source_key TEXT PRIMARY KEY, original_path TEXT NOT NULL, original_sha256 TEXT NOT NULL,
      original_bytes INTEGER NOT NULL, source_zip_zlib BLOB NOT NULL,
      archive_index_zlib BLOB NOT NULL, start_here_zlib BLOB NOT NULL,
      component_digest_manifest_json TEXT NOT NULL,
      provenance_status TEXT NOT NULL);

-- TABLE: arno_seven_final_repair_case_evidence
CREATE TABLE arno_seven_final_repair_case_evidence(
      case_id INTEGER PRIMARY KEY REFERENCES cases(id), final_patch_name TEXT NOT NULL,
      final_patch_sha256 TEXT NOT NULL, final_patch_zlib BLOB NOT NULL,
      final_result_name TEXT NOT NULL, final_result_sha256 TEXT NOT NULL, final_result_zlib BLOB NOT NULL,
      final_after_sarif_name TEXT NOT NULL, final_after_sarif_sha256 TEXT NOT NULL, final_after_sarif_zlib BLOB NOT NULL,
      initial_result_zlib BLOB, initial_before_sarif_zlib BLOB, initial_after_sarif_zlib BLOB,
      p1_initial_new_alert_count INTEGER NOT NULL, final_strong_new INTEGER NOT NULL,
      final_conservative_new INTEGER NOT NULL, final_scan_completed INTEGER NOT NULL,
      intervention_origin TEXT NOT NULL, functional_acceptance_status TEXT NOT NULL,
      causal_prevention_status TEXT NOT NULL, publication_qualification TEXT NOT NULL,
      exact_source_archive_key TEXT NOT NULL REFERENCES arno_seven_final_repair_archive(source_key));

-- TABLE: arno_sources
CREATE TABLE arno_sources(
  source_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, label TEXT NOT NULL, source_locator TEXT NOT NULL,
  source_sha256 TEXT, embedded_encoding TEXT, embedded_bytes BLOB, verification TEXT NOT NULL, notes TEXT
);

-- TABLE: arno_stage_ledger
CREATE TABLE arno_stage_ledger(
 stage_number INTEGER PRIMARY KEY, stage_name TEXT UNIQUE NOT NULL,
 status TEXT NOT NULL, detail TEXT, last_updated_utc TEXT NOT NULL
);

-- TABLE: artifact_regions
CREATE TABLE artifact_regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    pr_id INTEGER NOT NULL,
    pr_file_id INTEGER,
    path TEXT NOT NULL,
    region TEXT NOT NULL,
    language TEXT,
    generated INTEGER DEFAULT 0,
    vendor INTEGER DEFAULT 0,
    scanner_routes TEXT,
    confidence TEXT,
    evidence TEXT,
    mapping_version TEXT NOT NULL DEFAULT '1.0',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id),
    FOREIGN KEY(pr_file_id) REFERENCES pr_files(id)
);

-- TABLE: case_notes
CREATE TABLE case_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

-- TABLE: case_retrievals
CREATE TABLE case_retrievals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    stream_key TEXT NOT NULL,
    term TEXT NOT NULL,
    final_query TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_id, stream_key, term),
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

-- TABLE: case_tags
CREATE TABLE case_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_id, tag_id),
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(tag_id) REFERENCES tags(id)
);

-- TABLE: cases
CREATE TABLE cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    issue_id INTEGER NOT NULL,
    pr_id INTEGER NOT NULL,
    ai_cohort TEXT DEFAULT 'AI-unknown',
    downstream_signal TEXT,
    auto_tags TEXT,
    status TEXT DEFAULT 'queued',
    final_label TEXT DEFAULT 'Unclear',
    review_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_id, pr_id),
    FOREIGN KEY(repo_id) REFERENCES repos(id),
    FOREIGN KEY(issue_id) REFERENCES issues(id),
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: daemon_controls
CREATE TABLE daemon_controls (
    daemon_name TEXT PRIMARY KEY,
    desired_enabled INTEGER NOT NULL DEFAULT 0
        CHECK (desired_enabled IN (0, 1)),
    generation INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'stopped',
    partition TEXT NOT NULL,
    slurm_job_id TEXT,
    scheduler_state TEXT,
    worker_id TEXT,
    current_unit TEXT,
    detail TEXT,
    last_error TEXT,
    requested_at TEXT,
    submitted_at TEXT,
    started_at TEXT,
    heartbeat_at TEXT,
    stopped_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: distributed_result_imports
CREATE TABLE distributed_result_imports (
            task_id TEXT PRIMARY KEY,
            pool TEXT NOT NULL,
            worker_id TEXT,
            imported_at TEXT
                DEFAULT CURRENT_TIMESTAMP
        );

-- TABLE: excluded_cases
CREATE TABLE excluded_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT,
    issue_number INTEGER,
    pr_number INTEGER,
    reason TEXT NOT NULL,
    details TEXT,
    changed_files_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: github_rate_limits
CREATE TABLE github_rate_limits (
    resource TEXT PRIMARY KEY,
    limit_value INTEGER,
    remaining INTEGER,
    reset_at INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_sleep_until INTEGER,
    last_message TEXT
);

-- TABLE: issue_pr_links
CREATE TABLE issue_pr_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL,
    pr_id INTEGER NOT NULL,
    method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_id, pr_id),
    FOREIGN KEY(issue_id) REFERENCES issues(id),
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: issues
CREATE TABLE issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    github_id INTEGER,
    number INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    body TEXT,
    author TEXT,
    state TEXT,
    labels TEXT,
    comments_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    closed_at TEXT,
    word_count INTEGER DEFAULT 0,
    is_english INTEGER DEFAULT 1,
    UNIQUE(repo_id, number),
    FOREIGN KEY(repo_id) REFERENCES repos(id)
);

-- TABLE: mining_controller_batches
CREATE TABLE mining_controller_batches (
            batch_id TEXT PRIMARY KEY,
            batch_sequence INTEGER NOT NULL UNIQUE,
            exploration_share REAL NOT NULL,
            exploration_shards INTEGER NOT NULL,
            exploitation_shards INTEGER NOT NULL,
            known_processed INTEGER NOT NULL DEFAULT 0,
            known_new_candidates INTEGER NOT NULL DEFAULT 0,
            known_duplicate_prs INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

-- TABLE: mining_repo_batch_outcomes
CREATE TABLE mining_repo_batch_outcomes (
            task_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            batch_sequence INTEGER NOT NULL,
            lane TEXT NOT NULL,
            repo_full_name TEXT NOT NULL,
            raw_records INTEGER NOT NULL DEFAULT 0,
            processed_records INTEGER NOT NULL DEFAULT 0,
            new_prs INTEGER NOT NULL DEFAULT 0,
            already_seen_prs INTEGER NOT NULL DEFAULT 0,
            new_unique_candidates INTEGER NOT NULL DEFAULT 0,
            duplicate_candidates INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(task_id, repo_full_name)
        );

-- TABLE: mining_repo_cooldowns
CREATE TABLE mining_repo_cooldowns (
            repo_full_name TEXT PRIMARY KEY,
            triggered_by_sequence INTEGER NOT NULL,
            until_sequence INTEGER NOT NULL,
            reason TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

-- TABLE: pipeline_events
CREATE TABLE pipeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: pr_files
CREATE TABLE pr_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    status TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    patch TEXT,
    category TEXT,
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: pr_region_profiles
CREATE TABLE pr_region_profiles (
    case_id INTEGER PRIMARY KEY,
    pr_id INTEGER NOT NULL,
    primary_region TEXT NOT NULL,
    region_counts_json TEXT NOT NULL,
    scanner_routes_json TEXT NOT NULL,
    language_json TEXT,
    file_count INTEGER DEFAULT 0,
    mapping_version TEXT NOT NULL DEFAULT '1.0',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: pull_requests
CREATE TABLE pull_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    body TEXT,
    author TEXT,
    state TEXT,
    merged INTEGER DEFAULT 0,
    head_ref TEXT,
    base_ref TEXT,
    head_sha TEXT,
    base_sha TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changed_files_count INTEGER DEFAULT 0,
    commits_count INTEGER DEFAULT 0,
    review_comments_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    closed_at TEXT,
    merged_at TEXT,
    UNIQUE(repo_id, number),
    FOREIGN KEY(repo_id) REFERENCES repos(id)
);

-- TABLE: repo_eligibility
CREATE TABLE repo_eligibility (
    repo_full_name TEXT PRIMARY KEY,
    stars INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,
    fork INTEGER DEFAULT 0,
    has_issues INTEGER DEFAULT 1,
    primary_language TEXT,
    language_bytes_json TEXT,
    total_language_bytes INTEGER DEFAULT 0,
    javascript_bytes INTEGER DEFAULT 0,
    typescript_bytes INTEGER DEFAULT 0,
    js_ts_bytes INTEGER DEFAULT 0,
    js_ts_share REAL DEFAULT 0.0,
    min_stars INTEGER DEFAULT 0,
    min_js_ts_share REAL DEFAULT 0.0,
    eligible INTEGER DEFAULT 0,
    reason TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: repos
CREATE TABLE repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT UNIQUE NOT NULL,
    html_url TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    language TEXT,
    archived INTEGER DEFAULT 0,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: retrieval_queries
CREATE TABLE retrieval_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_key TEXT NOT NULL,
    term TEXT NOT NULL,
    final_query TEXT NOT NULL UNIQUE,
    raw_count INTEGER DEFAULT 0,
    unique_count INTEGER DEFAULT 0,
    eligible_count INTEGER DEFAULT 0,
    candidate_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    repo_filter_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    excluded_count INTEGER DEFAULT 0,
    search_window_count INTEGER DEFAULT 0,
    split_window_count INTEGER DEFAULT 0,
    probe_count INTEGER DEFAULT 0,
    reported_total_count INTEGER DEFAULT 0,
    next_page INTEGER DEFAULT 1,
    exhausted INTEGER DEFAULT 0,
    last_error TEXT,
    status TEXT DEFAULT 'pending',
    last_run_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: scanner_findings
CREATE TABLE scanner_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    pr_id INTEGER NOT NULL,
    scanner TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    severity TEXT,
    rule_id TEXT,
    cwe TEXT,
    file_path TEXT,
    line INTEGER,
    description TEXT,
    evidence TEXT,
    raw_json TEXT,
    introduced INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: scanner_jobs
CREATE TABLE scanner_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT,
    worker_id TEXT,
    route_reason TEXT,
    UNIQUE(case_id, job_type),
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

-- TABLE: scanner_runs
CREATE TABLE scanner_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    pr_id INTEGER NOT NULL,
    scanner TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    stdout TEXT,
    stderr TEXT,
    FOREIGN KEY(pr_id) REFERENCES pull_requests(id)
);

-- TABLE: tags
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT DEFAULT 'manual',
    color TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: upstream_features
CREATE TABLE upstream_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER UNIQUE NOT NULL,
    has_code_block INTEGER DEFAULT 0,
    has_inline_code INTEGER DEFAULT 0,
    has_traceback_or_log INTEGER DEFAULT 0,
    has_file_path INTEGER DEFAULT 0,
    has_function_or_class INTEGER DEFAULT 0,
    has_dependency_or_version INTEGER DEFAULT 0,
    has_suggested_fix INTEGER DEFAULT 0,
    has_ai_marker INTEGER DEFAULT 0,
    feature_json TEXT,
    FOREIGN KEY(issue_id) REFERENCES issues(id)
);

-- TABLE: worker_heartbeats
CREATE TABLE worker_heartbeats (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL,
    mode TEXT,
    status TEXT NOT NULL,
    detail TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- INDEX: arno_chat_artifacts_case_role
CREATE INDEX arno_chat_artifacts_case_role ON arno_chat_evidence_objects(case_id,role);

-- INDEX: arno_chat_f_rule_case
CREATE INDEX arno_chat_f_rule_case ON arno_chat_codeql_findings(case_id,rule_id,new_vs_baseline);

-- INDEX: arno_chat_f_run_new
CREATE INDEX arno_chat_f_run_new ON arno_chat_codeql_findings(run_id,new_vs_baseline);

-- INDEX: arno_chat_m_case_method
CREATE INDEX arno_chat_m_case_method ON arno_chat_codeql_metrics(case_id,method);

-- INDEX: idx_artifact_regions_case
CREATE INDEX idx_artifact_regions_case ON artifact_regions(case_id);

-- INDEX: idx_artifact_regions_region
CREATE INDEX idx_artifact_regions_region ON artifact_regions(region);

-- INDEX: idx_case_retrievals_case
CREATE INDEX idx_case_retrievals_case ON case_retrievals(case_id);

-- INDEX: idx_case_retrievals_term
CREATE INDEX idx_case_retrievals_term ON case_retrievals(term);

-- INDEX: idx_cases_status
CREATE INDEX idx_cases_status ON cases(status);

-- INDEX: idx_daemon_controls_enabled
CREATE INDEX idx_daemon_controls_enabled
ON daemon_controls(desired_enabled, state);

-- INDEX: idx_excluded_cases_reason
CREATE INDEX idx_excluded_cases_reason ON excluded_cases(reason);

-- INDEX: idx_findings_case
CREATE INDEX idx_findings_case ON scanner_findings(case_id);

-- INDEX: idx_mining_repo_outcomes_batch
CREATE INDEX idx_mining_repo_outcomes_batch
        ON mining_repo_batch_outcomes(batch_sequence, lane);

-- INDEX: idx_mining_repo_outcomes_repo
CREATE INDEX idx_mining_repo_outcomes_repo
        ON mining_repo_batch_outcomes(repo_full_name, batch_sequence);

-- INDEX: idx_pr_files_pr
CREATE INDEX idx_pr_files_pr ON pr_files(pr_id);

-- INDEX: idx_pr_region_profiles_region
CREATE INDEX idx_pr_region_profiles_region ON pr_region_profiles(primary_region);

-- INDEX: idx_repo_eligibility_eligible
CREATE INDEX idx_repo_eligibility_eligible
ON repo_eligibility(
    eligible,
    js_ts_share
);

-- INDEX: idx_scanner_jobs_case
CREATE INDEX idx_scanner_jobs_case ON scanner_jobs(case_id);

-- INDEX: idx_scanner_jobs_status
CREATE INDEX idx_scanner_jobs_status ON scanner_jobs(status, priority, created_at);

-- VIEW: arno_v_D7_roots_not_in_M233
CREATE VIEW arno_v_D7_roots_not_in_M233 AS
   SELECT r.root_id,r.case_id,r.coding_status
   FROM arno_root_decisions r LEFT JOIN arno_d7_final_M_roots_233 d
   ON d.root_id=r.root_id WHERE d.root_id IS NULL;

-- VIEW: arno_v_chat_artifact_inventory
CREATE VIEW arno_v_chat_artifact_inventory AS
 SELECT o.case_id,o.run_id,m.method,o.role,o.source_locator,o.sha256,o.original_bytes,
 o.compression,o.verification_status
 FROM arno_chat_evidence_objects o JOIN arno_chat_codeql_metrics m ON m.run_id=o.run_id;

-- VIEW: arno_v_chat_case_comparison
CREATE VIEW arno_v_chat_case_comparison AS
 SELECT case_label,case_id,run_id,method,source_kind,
 baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,
 functional_status,receipt_status,codeql_version,codeql_suite,sarif_sha256,patch_sha256,provenance_status
 FROM arno_chat_codeql_metrics;

-- VIEW: arno_v_chat_new_codeql_findings
CREATE VIEW arno_v_chat_new_codeql_findings AS
 SELECT f.case_id,f.run_id,m.method,f.rule_id,f.file_path,f.line,f.message,
 f.signature_sha256,f.matches_historical_p1,f.raw_result_json
 FROM arno_chat_codeql_findings f JOIN arno_chat_codeql_metrics m ON m.run_id=f.run_id
 WHERE f.new_vs_baseline=1;

-- VIEW: arno_v_first122
CREATE VIEW arno_v_first122 AS SELECT c.id as case_id,c.status as miner_status,
 a.issue_purpose,a.instruction_specificity,a.request_scope,a.pr_purpose,
 a.goal_alignment,a.implementation_final,a.risk_final FROM cases c
 JOIN arno_classifications a ON a.case_id=c.id;

-- VIEW: arno_v_new70_finding_change_evidence
CREATE VIEW arno_v_new70_finding_change_evidence AS
 SELECT f.canonical_finding_id,f.case_id,f.repository,f.pr_number,f.finding_family,f.scanner,
 f.rule_id,f.description,m.mapping_status,m.producing_change_id,m.mapping_basis,
 m.no_mapping_reason,p.change_description,p.changed_locations,p.pr_diff_evidence
 FROM arno_new70_final_findings f
 JOIN arno_new70_final_finding_maps m USING(canonical_finding_id)
 LEFT JOIN arno_new70_final_producing_changes p ON p.producing_change_id=m.producing_change_id;

-- VIEW: arno_v_raw_positive198
CREATE VIEW arno_v_raw_positive198 AS SELECT c.id AS case_id,COUNT(f.id) AS introduced_finding_rows
 FROM cases c JOIN scanner_findings f ON f.case_id=c.id
 WHERE f.introduced=1 GROUP BY c.id;

COMMIT;
