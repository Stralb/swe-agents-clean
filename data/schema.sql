CREATE TABLE study_D_root_evidence_index (
      root_id TEXT PRIMARY KEY REFERENCES study_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),
      producing_change_count INTEGER NOT NULL,
      pass_A_evidence_items INTEGER NOT NULL,
      pass_B_evidence_items INTEGER NOT NULL,
      issue_preintro_human_status TEXT,
      true_base_target_status TEXT,bounded_repo_search_status TEXT,
      project_instructions_status TEXT,dependency_toolchain_status TEXT,
      external_guidance_status TEXT,chronology_status TEXT,
      frozen_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES study_sources(source_key),
      evidence_kind TEXT NOT NULL DEFAULT 'PRE_ADJUDICATION_EVIDENCE_PACKET'
    );

CREATE TABLE study_annotation_events(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 case_id INTEGER NOT NULL REFERENCES study_classifications(case_id),
 dimension TEXT NOT NULL, event_stage TEXT NOT NULL, label_value TEXT,
 source_key TEXT NOT NULL REFERENCES study_sources(source_key),
 notes TEXT, UNIQUE(case_id,dimension,event_stage)
);

CREATE TABLE study_archive_vault_chunks(
    object_key TEXT NOT NULL REFERENCES study_archive_vault_objects(object_key),
    sequence INTEGER NOT NULL,bytes BLOB NOT NULL,content_sha256 TEXT NOT NULL,
    PRIMARY KEY(object_key,sequence)
   );

CREATE TABLE study_archive_vault_members(
    archive_name TEXT NOT NULL,member_path TEXT NOT NULL,case_id TEXT,
    role TEXT NOT NULL,sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    indexed_in_master INTEGER NOT NULL,matched_master_tables TEXT,
    PRIMARY KEY(archive_name,member_path)
   );

CREATE TABLE study_archive_vault_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

CREATE TABLE study_archive_vault_objects(
    object_key TEXT PRIMARY KEY,source_kind TEXT NOT NULL,source_locator TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
    segment_count INTEGER NOT NULL,case_id INTEGER,source_key TEXT
   );

CREATE TABLE study_archive_vault_sources(
    source_key TEXT PRIMARY KEY REFERENCES study_sources(source_key),
    kind TEXT NOT NULL,original_locator TEXT NOT NULL,expected_sha256 TEXT,
    vault_object_key TEXT,coverage_status TEXT NOT NULL
   );

CREATE TABLE study_c6_bootstrap_reproduction_artifacts(
   artifact_key TEXT PRIMARY KEY, original_relative_path TEXT NOT NULL,
   sha256 TEXT NOT NULL,content_zlib BLOB NOT NULL,original_bytes INTEGER NOT NULL);

CREATE TABLE study_c6_independent_bootstrap_replication(
  variable TEXT PRIMARY KEY, effect TEXT NOT NULL, original_point_estimate REAL NOT NULL,
  independent_point_estimate REAL NOT NULL, original_ci_low REAL NOT NULL,
  original_ci_high REAL NOT NULL, independent_ci_low REAL NOT NULL,independent_ci_high REAL NOT NULL,
  lower_bound_abs_difference REAL NOT NULL,upper_bound_abs_difference REAL NOT NULL,
  frozen_num_repo_blocks INTEGER NOT NULL,largest_block INTEGER NOT NULL,
  seed INTEGER NOT NULL,bootstrap_replicates INTEGER NOT NULL,
  evidence_status TEXT NOT NULL,run_utc TEXT NOT NULL);

CREATE TABLE study_canonical_id_pc_links(
  canonical_finding_id TEXT PRIMARY KEY,
  cohort TEXT NOT NULL,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL REFERENCES study_mechanism_selection(decision_id),
  root_id TEXT NOT NULL REFERENCES study_root_decisions(root_id),
  source_key TEXT NOT NULL REFERENCES study_sources(source_key),
  detailed_step1_import_status TEXT NOT NULL CHECK(detailed_step1_import_status IN ('PENDING_ORIGINAL_SHEET','PENDING_NEW70_FINAL_SHEET')),
  FOREIGN KEY(cohort,producing_change_id) REFERENCES study_frozen_broad_attribution(cohort,producing_change_id));

CREATE TABLE study_imported_codeql_findings(
 finding_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES study_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 result_index INTEGER NOT NULL,rule_id TEXT NOT NULL,file_path TEXT NOT NULL,
 line INTEGER,column INTEGER,level TEXT,message TEXT NOT NULL,
 signature_sha256 TEXT NOT NULL,
 new_vs_baseline INTEGER NOT NULL CHECK(new_vs_baseline IN(0,1)),
 matches_historical_p1 INTEGER NOT NULL CHECK(matches_historical_p1 IN(0,1)),
 raw_result_json TEXT NOT NULL,
 UNIQUE(run_id,result_index));

CREATE TABLE study_imported_codeql_metrics (
 run_id TEXT PRIMARY KEY REFERENCES study_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 case_label TEXT NOT NULL, method TEXT NOT NULL,
 source_kind TEXT NOT NULL, source_tree_sha256 TEXT NOT NULL, source_zip_sha256 TEXT NOT NULL,
 baseline_total INTEGER NOT NULL, after_total INTEGER NOT NULL,
 new_vs_baseline INTEGER NOT NULL, historical_p1_new INTEGER NOT NULL,
 historical_p1_remaining INTEGER,
 codeql_version TEXT NOT NULL, codeql_suite TEXT NOT NULL, sarif_sha256 TEXT NOT NULL,
 patch_sha256 TEXT, receipt_status TEXT NOT NULL, functional_status TEXT NOT NULL,
 provenance_status TEXT NOT NULL, result_metadata_json TEXT NOT NULL);

CREATE TABLE study_imported_evidence_objects(
 artifact_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES study_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 role TEXT NOT NULL, source_locator TEXT NOT NULL,
 sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL,
 compression TEXT NOT NULL,content_zlib BLOB,verification_status TEXT NOT NULL,
 UNIQUE(run_id,role,sha256));

CREATE TABLE study_imported_ingest_ledger(
 batch_id TEXT PRIMARY KEY,ingested_utc TEXT NOT NULL,
 source_manifest_sha256 TEXT NOT NULL,completed_runs INTEGER NOT NULL,
 patch_count INTEGER NOT NULL,sarif_count INTEGER NOT NULL,
 finding_count INTEGER NOT NULL,missing_receipts_json TEXT NOT NULL,
 preexisting_counts_json TEXT NOT NULL,notes TEXT);

CREATE TABLE study_imported_pending_runs(
 run_id TEXT PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id),
 method TEXT NOT NULL,status TEXT NOT NULL,agent_input_basename TEXT,
 missing_artifacts_json TEXT NOT NULL,notes TEXT);

CREATE TABLE study_choice_case_split(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),partition TEXT NOT NULL,
 rank INTEGER UNIQUE NOT NULL,selection_hash TEXT UNIQUE NOT NULL,
 pc_count INTEGER NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_choice_eligible_pc(
 pc_id TEXT PRIMARY KEY REFERENCES study_mechanism_selection(decision_id),
 case_id INTEGER NOT NULL REFERENCES study_choice_case_split(case_id),
 partition TEXT NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_claim_status_supersession_20261029 (claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,current_evidence_status TEXT NOT NULL,evidence TEXT NOT NULL,caveat TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_classifications(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id), review_number INTEGER UNIQUE NOT NULL,
 issue_request_summary TEXT, issue_purpose TEXT, instruction_specificity TEXT, request_scope TEXT,
 pr_stated_goal_summary TEXT, pr_purpose TEXT, goal_alignment TEXT,
 implementation_summary TEXT, implementation_first_pass TEXT, implementation_correction TEXT, implementation_final TEXT,
 risk_first_pass TEXT, risk_correction TEXT, risk_final TEXT, risk_human_review TEXT,
 agent_tool TEXT, agent_provenance TEXT,
 original_row_json TEXT NOT NULL, imported_source_key TEXT NOT NULL REFERENCES study_sources(source_key),
 raw_row_sha256 TEXT NOT NULL
);

CREATE TABLE study_codeql_oct19_original_archive_inventory (
    source_key TEXT PRIMARY KEY REFERENCES study_sources(source_key),
    file_name TEXT NOT NULL UNIQUE,relative_path TEXT NOT NULL UNIQUE,
    original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    member_count INTEGER,handling TEXT NOT NULL,
    original_manifest_source_key TEXT NOT NULL REFERENCES study_sources(source_key)
  );

CREATE TABLE study_cohort_membership(
        case_id INTEGER NOT NULL REFERENCES cases(id),
        cohort_key TEXT NOT NULL, membership_label TEXT NOT NULL,
        source_key TEXT NOT NULL REFERENCES study_sources(source_key),
        PRIMARY KEY(case_id,cohort_key)
    );

CREATE TABLE study_d7_final_M_roots_233(
    root_id TEXT PRIMARY KEY REFERENCES study_root_decisions(root_id),
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
    source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    final_adjudication_status TEXT NOT NULL DEFAULT 'FINAL_D7_M_SUBSET'
 );

CREATE TABLE study_d7_final_roots_342 (
      root_id TEXT PRIMARY KEY REFERENCES study_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),repository TEXT NOT NULL,
      pc_count INTEGER NOT NULL,final_route TEXT NOT NULL CHECK(final_route IN ('M','H','T')),
      final_tier TEXT NOT NULL,d7_cohort TEXT NOT NULL,final_route_confidence TEXT NOT NULL,
      final_explanation_confidence TEXT,chronology_status TEXT NOT NULL,
      evidence_complete TEXT NOT NULL,evidence_ids TEXT,
      adjudication_rationale TEXT NOT NULL,original_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_evidence_assets(source_path TEXT PRIMARY KEY, cohort TEXT NOT NULL, artifact_role TEXT NOT NULL, source_sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL, content_zlib BLOB NOT NULL, verification TEXT NOT NULL);

CREATE TABLE study_excluded_cases(
        case_id INTEGER PRIMARY KEY REFERENCES cases(id),
        repository TEXT, pr_number INTEGER, validation_type TEXT,
        historical_verdict TEXT NOT NULL, old_finding_count INTEGER,
        corrected_finding_count INTEGER, exclusion_reason TEXT NOT NULL,
        original_row_json TEXT NOT NULL, source_key TEXT NOT NULL REFERENCES study_sources(source_key)
    );

CREATE TABLE study_exp_transfer_files(
    source_path TEXT PRIMARY KEY,
    source_group TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    original_byte_count INTEGER NOT NULL,
    original_zlib BLOB NOT NULL,
    provenance_status TEXT NOT NULL DEFAULT 'ORIGINAL_UPLOAD_VERIFIED'
 );

CREATE TABLE study_experiment_runs(
 run_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 root_id TEXT REFERENCES study_root_decisions(root_id), experiment_family TEXT NOT NULL,
 treatment TEXT, prompt_blob BLOB, run_metadata_json TEXT, status TEXT NOT NULL
);

CREATE TABLE study_experiment_scans(
 scan_id TEXT PRIMARY KEY, run_id TEXT REFERENCES study_experiment_runs(run_id),
 scanner TEXT NOT NULL, scanner_version TEXT, rule_id TEXT,
 raw_result_blob BLOB, result_json TEXT, execution_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE study_frozen_broad_attribution(
  cohort TEXT NOT NULL CHECK(cohort IN('original122','new70')),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL UNIQUE REFERENCES study_mechanism_selection(decision_id),
  case_id INTEGER NOT NULL REFERENCES cases(id),
  root_id TEXT NOT NULL REFERENCES study_root_decisions(root_id),
  attribution TEXT NOT NULL,
  attribution_basis TEXT,
  attribution_reason TEXT,
  source_key TEXT NOT NULL REFERENCES study_sources(source_key),
  provenance_kind TEXT NOT NULL,
  PRIMARY KEY(cohort,producing_change_id));

CREATE TABLE study_generated_patches(
 patch_id TEXT PRIMARY KEY, run_id TEXT REFERENCES study_experiment_runs(run_id),
 content_sha256 TEXT, patch_blob BLOB, patch_uri TEXT, authenticity_status TEXT NOT NULL,
 notes TEXT
);

CREATE TABLE study_matched_control_C1_opportunity(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    is_positive INTEGER NOT NULL CHECK(is_positive IN(0,1)),
    scanner_opportunity_signature TEXT,
    source_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_matched_control_C3_blind_inputs(
    blind_id TEXT PRIMARY KEY,
    positive_case_id INTEGER NOT NULL REFERENCES study_matched_control_pairs_C2(positive_case_id),
    control_case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
    issue_blind_json TEXT NOT NULL,
    pr_blind_json TEXT NOT NULL,
    context_raw_json TEXT NOT NULL,
    blinded_manifest_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_matched_control_C3_impl_packets(
    blind_id TEXT NOT NULL REFERENCES study_matched_control_C3_blind_inputs(blind_id),
    packet_kind TEXT NOT NULL CHECK(packet_kind IN('raw','blind')),
    original_sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    compressed_bytes BLOB NOT NULL,
    source_path TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    PRIMARY KEY(blind_id,packet_kind));

CREATE TABLE study_matched_control_pairs_C2(
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
    source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    provenance_kind TEXT NOT NULL DEFAULT 'C2_MATCHED_CONTROL_NOT_OUTCOME');

CREATE TABLE study_matched_control_unmatched_C2(
    positive_case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    reason TEXT NOT NULL,original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key));

CREATE TABLE study_mechanism_selection(
 decision_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 producing_change_id TEXT, choice_summary TEXT, evidence_json TEXT,
 evidence_source_key TEXT REFERENCES study_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE study_new70_canonical_prelim_254(
    preliminary_finding_id TEXT PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    qc_status TEXT,
    finding_family TEXT, rule_id TEXT, canonical_finding TEXT,
    scanner TEXT, raw_scanner_row_count INTEGER,
    original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    freeze_status TEXT NOT NULL DEFAULT 'PRE_QC_NOT_FINAL'
 );

CREATE TABLE study_new70_context_frozen(
   case_id INTEGER PRIMARY KEY REFERENCES study_new70_source_inputs(case_id),
   review_number INTEGER NOT NULL,issue_author TEXT,
   author_association TEXT,human_review_before_merge TEXT,
   original_context_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES study_sources(source_key)
 );

CREATE TABLE study_new70_final_finding_maps (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES study_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, mapping_status TEXT NOT NULL CHECK(mapping_status IN ('Mapped','Not isolated')),
 producing_change_id TEXT REFERENCES study_new70_final_producing_changes(producing_change_id),
 mapping_basis TEXT, changed_locations TEXT, diff_evidence TEXT,
 frozen_source_raw_ids TEXT NOT NULL, no_mapping_reason TEXT,
 attribution_status TEXT NOT NULL,
 original_row_json TEXT NOT NULL,
 CHECK((mapping_status='Mapped' AND producing_change_id IS NOT NULL) OR (mapping_status='Not isolated' AND producing_change_id IS NULL)));

CREATE TABLE study_new70_final_findings (
 canonical_finding_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, repository TEXT NOT NULL,
 pr_number TEXT NOT NULL, finding_family TEXT NOT NULL, scanner TEXT NOT NULL,
 rule_id TEXT, description TEXT NOT NULL, primary_file TEXT, severity TEXT,
 raw_scanner_row_count INTEGER NOT NULL, frozen_qc_status TEXT NOT NULL,
 reviewer_identity_status TEXT NOT NULL,
 original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_final_freeze_manifest (
 metric TEXT PRIMARY KEY, stored_value TEXT NOT NULL, verification_status TEXT NOT NULL, explanation TEXT);

CREATE TABLE study_new70_final_method_qc (
 record_key TEXT PRIMARY KEY, stage TEXT NOT NULL, metric TEXT, reported_status TEXT,
 original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_final_producing_changes (
 producing_change_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, repository TEXT NOT NULL,
 pr_number TEXT NOT NULL, change_description TEXT NOT NULL, mapping_bases TEXT NOT NULL,
 changed_locations TEXT NOT NULL, pr_diff_evidence TEXT NOT NULL,
 pr_diff_source TEXT NOT NULL, canonical_finding_count INTEGER NOT NULL,
 original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_final_evidence_status (
    claim_key TEXT PRIMARY KEY,rq TEXT NOT NULL,verification TEXT NOT NULL,
    claim_text TEXT NOT NULL,source_table TEXT NOT NULL,qualifications TEXT NOT NULL,
    replaces_prior_missing_artifact_flag INTEGER NOT NULL);

CREATE TABLE study_new70_final_raw_finding_links (
 raw_finding_id TEXT PRIMARY KEY, canonical_finding_id TEXT NOT NULL REFERENCES study_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, scanner TEXT NOT NULL, finding_rule TEXT,
 original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_final_source_blobs (
 source_key TEXT PRIMARY KEY, original_name TEXT NOT NULL, container TEXT NOT NULL,
 byte_size INTEGER NOT NULL, sha256 TEXT NOT NULL, content_zlib BLOB NOT NULL,
 evidence_state TEXT NOT NULL);

CREATE TABLE study_new70_final_source_id_audit (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES study_new70_final_findings(canonical_finding_id),
 original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_final_unresolved (
 canonical_finding_id TEXT PRIMARY KEY REFERENCES study_new70_final_findings(canonical_finding_id),
 case_id INTEGER NOT NULL, explanation TEXT NOT NULL, original_row_json TEXT NOT NULL);

CREATE TABLE study_new70_id_version_conflicts(
    preliminary_finding_id TEXT PRIMARY KEY REFERENCES study_new70_canonical_prelim_254(preliminary_finding_id),
    preliminary_case_id INTEGER NOT NULL REFERENCES cases(id),
    later_provenance_case_id INTEGER NOT NULL REFERENCES cases(id),
    id_collision_status TEXT NOT NULL,
    audit_source_key TEXT NOT NULL REFERENCES study_sources(source_key)
 );

CREATE TABLE study_new70_phase8_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES study_new70_source_inputs(case_id),
              repository TEXT,case_evidence_summary TEXT,producing_change_profile TEXT,
              qc_status TEXT,qc_note TEXT,frozen_synthesis_input_sha256 TEXT,
              full_original_row_json TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_new70_phase9_full_source (
              case_id INTEGER PRIMARY KEY REFERENCES study_new70_phase9_risk(case_id),
              complete_original_row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_new70_phase9_risk(
   case_id INTEGER PRIMARY KEY REFERENCES study_new70_source_inputs(case_id),
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
   source_key TEXT NOT NULL REFERENCES study_sources(source_key),
   label_kind TEXT NOT NULL DEFAULT 'PROVISIONAL_ORIGINAL_PHASE9'
 );

CREATE TABLE study_new70_phase9_risk_events(
    case_id INTEGER NOT NULL REFERENCES study_new70_phase9_risk(case_id),
    event_stage TEXT NOT NULL CHECK(event_stage IN ('first_pass','qc_correction','final')),
    label TEXT NOT NULL,notes TEXT,source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    PRIMARY KEY(case_id,event_stage));

CREATE TABLE study_new70_scanner_raw_frozen(
   raw_finding_id INTEGER PRIMARY KEY,
   case_id INTEGER NOT NULL REFERENCES study_new70_source_inputs(case_id),
   pr_id INTEGER NOT NULL,scanner TEXT NOT NULL,
   finding_type TEXT,severity TEXT,rule_id TEXT,cwe TEXT,
   file_path TEXT,line_number INTEGER,description TEXT,evidence TEXT,
   raw_json TEXT,introduced INTEGER NOT NULL CHECK(introduced IN(0,1)),
   created_at TEXT,original_row_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES study_sources(source_key),
   evidence_stage TEXT NOT NULL DEFAULT 'RAW_FROZEN_NOT_FINAL');

CREATE TABLE study_new70_source_inputs(
   case_id INTEGER PRIMARY KEY REFERENCES cases(id),
   pr_id INTEGER NOT NULL REFERENCES pull_requests(id),
   review_number INTEGER NOT NULL UNIQUE,
   issue_title TEXT,issue_body TEXT,pr_title TEXT,pr_body TEXT,
   case_mapping_json TEXT NOT NULL,blind_issue_json TEXT NOT NULL,
   blind_pr_json TEXT NOT NULL,stage4b_index_json TEXT NOT NULL,
   evidence_filename TEXT,evidence_completeness TEXT,
   raw_promoted_flag INTEGER NOT NULL CHECK(raw_promoted_flag IN(0,1)),
   classification_status TEXT NOT NULL DEFAULT 'SOURCE_ONLY',
   source_key TEXT NOT NULL REFERENCES study_sources(source_key)
 );

CREATE TABLE study_original_case_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES study_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_original_full_risk_source (
              case_id INTEGER PRIMARY KEY REFERENCES study_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_original_step1_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES study_canonical_id_pc_links(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),rule_id TEXT,severity TEXT,scanner TEXT,
              finding_description TEXT,row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_original_step2_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES study_original_step1_detail(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),source_producing_change_id TEXT NOT NULL,
              mapping_status TEXT,changed_locations TEXT,diff_evidence TEXT,
              row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_original_step3_detail (
              source_producing_change_id TEXT PRIMARY KEY,
              case_id INTEGER NOT NULL REFERENCES cases(id),first_pass_attribution TEXT,
              first_pass_basis TEXT,qc_correction TEXT,final_attribution TEXT NOT NULL,
              attribution_basis TEXT,attribution_reason TEXT,row_json TEXT NOT NULL,
              original_row_number INTEGER NOT NULL,source_key TEXT NOT NULL REFERENCES study_sources(source_key)
            );

CREATE TABLE study_owp14_exact_scan_baseline_links_20261029 (
    case_id INTEGER NOT NULL,arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    baseline_sarif_sha256 TEXT NOT NULL,original_input_packet_sha256 TEXT NOT NULL,
    screen65_first_before_member_path TEXT NOT NULL,
    codeql_version TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,
    exact_match_status TEXT NOT NULL DEFAULT 'BYTE_IDENTICAL_FIRST_WAVE_SARIF_AND_PACKET_SHA',
    historical_pr_revision_equivalence TEXT NOT NULL DEFAULT 'NOT_VERIFIED',
    original_report_source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    PRIMARY KEY(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES study_rq3_owp14_run_scans(case_id,arm),
    FOREIGN KEY(case_id,arm) REFERENCES study_owp14_original_input_packet_inventory_20261029(case_id,arm),
    FOREIGN KEY(case_id) REFERENCES cases(id)
  );

CREATE TABLE study_owp14_fresh_o_reruns_20261031(
 run_id TEXT PRIMARY KEY REFERENCES study_experiment_runs(run_id),
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

CREATE TABLE study_owp14_input_repo_equivalence_20261029 (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    repo_tree_sha256 TEXT NOT NULL,repo_member_count INTEGER NOT NULL,
    repo_total_bytes INTEGER NOT NULL,source_packet_arms INTEGER NOT NULL,
    distinct_issue_md_hashes INTEGER NOT NULL,
    input_equivalence_status TEXT NOT NULL,
    historical_pr_revision_status TEXT NOT NULL,
    historical_issue_wording_status TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES study_sources(source_key)
  );

CREATE TABLE study_owp14_original_input_packet_inventory_20261029 (
    case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
    original_filename TEXT NOT NULL UNIQUE,original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,historical_issue_text_verified INTEGER NOT NULL,
    baseline_has_historical_rule INTEGER NOT NULL,historical_target_rule TEXT,
    has_exact_original_scan_result_link INTEGER NOT NULL CHECK(has_exact_original_scan_result_link IN (0,1)),
    packet_source_key TEXT NOT NULL REFERENCES study_sources(source_key),
    packet_index_source_key TEXT NOT NULL REFERENCES study_sources(source_key),PRIMARY KEY(case_id,arm));

CREATE TABLE study_patch_fragment_lineage(
    patch_key TEXT NOT NULL REFERENCES study_recovered_agent_patch_bytes(patch_key),
    source_path TEXT NOT NULL REFERENCES study_exp_transfer_files(source_path),
    sequence_number INTEGER NOT NULL,
    PRIMARY KEY(patch_key,source_path)
 );

CREATE TABLE study_pc_root_lineage(
       producing_change_id TEXT PRIMARY KEY,
       case_id INTEGER NOT NULL REFERENCES cases(id),
       root_id TEXT NOT NULL REFERENCES study_root_decisions(root_id),
       original_c5_row_json TEXT NOT NULL,
       source_key TEXT NOT NULL REFERENCES study_sources(source_key)
    );

CREATE TABLE study_evidence_audit_v6_20261028(
  evidence_key TEXT PRIMARY KEY,rq TEXT NOT NULL,status TEXT NOT NULL,
  source_locator TEXT NOT NULL,verified_fact TEXT NOT NULL,
  limitation TEXT NOT NULL,audited_at_utc TEXT NOT NULL);

CREATE TABLE study_postmerge_evidence_status_20261028(
   audit_key TEXT PRIMARY KEY,rq TEXT NOT NULL,evidence_status TEXT NOT NULL,
   quantitative_summary TEXT NOT NULL,original_evidence_locator TEXT NOT NULL,
   evidence_qualification TEXT NOT NULL,verified_at_utc TEXT NOT NULL);

CREATE TABLE study_evidence_status(claim_key TEXT PRIMARY KEY, rq TEXT NOT NULL, source_asset TEXT NOT NULL REFERENCES study_evidence_assets(source_path), status TEXT NOT NULL, limitations TEXT NOT NULL);

CREATE TABLE study_recovered_agent_patch_bytes(
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

CREATE TABLE study_recovery_claim_events_20261028(
   claim_key TEXT PRIMARY KEY, evidence_status TEXT NOT NULL, precise_claim TEXT NOT NULL,
   source_locator TEXT NOT NULL, qualification TEXT NOT NULL, audited_at_utc TEXT NOT NULL);

CREATE TABLE study_recovery_v05_sources (
              source_key TEXT PRIMARY KEY REFERENCES study_sources(source_key),
              capsule_original_key TEXT NOT NULL, originating_member TEXT NOT NULL,
              original_bytes_size INTEGER NOT NULL,
              original_sha256 TEXT NOT NULL
            );

CREATE TABLE study_root_decisions(
 root_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 mechanism_decision_id TEXT REFERENCES study_mechanism_selection(decision_id),
 producing_change_ids_json TEXT, root_coding_json TEXT,
 evidence_source_key TEXT REFERENCES study_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE study_rq2_c5_controls(blind_id TEXT PRIMARY KEY, repository TEXT, issue_number TEXT, pr_number TEXT, issue_purpose TEXT, instruction_specificity TEXT, pr_purpose TEXT, goal_alignment TEXT, implementation_pattern TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES study_evidence_assets(source_path), review_status TEXT NOT NULL);

CREATE TABLE study_rq2_c5_corrections(blind_id TEXT PRIMARY KEY REFERENCES study_rq2_c5_controls(blind_id), priority TEXT, corrected_fields TEXT, reason TEXT, original_row_json TEXT NOT NULL, human_verified INTEGER NOT NULL DEFAULT 0, review_provenance TEXT NOT NULL);

CREATE TABLE study_rq2_c5_stability(dimension TEXT PRIMARY KEY, original_row_json TEXT NOT NULL, interpretation TEXT NOT NULL);

CREATE TABLE study_rq2_c6_contingency(scope TEXT NOT NULL, variable TEXT NOT NULL, positive_category TEXT NOT NULL, control_category TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY(scope,variable,positive_category,control_category));

CREATE TABLE study_rq2_c6_omnibus(variable TEXT PRIMARY KEY, n_pairs INTEGER, test TEXT, test_statistic REAL, reported_p REAL, original_row_json TEXT NOT NULL, reproducibility_status TEXT NOT NULL);

CREATE TABLE study_rq2_c6_pairs(pair_index INTEGER PRIMARY KEY, positive_case_id INTEGER NOT NULL UNIQUE, control_case_id INTEGER NOT NULL UNIQUE, control_blind_id TEXT NOT NULL UNIQUE REFERENCES study_rq2_c5_controls(blind_id), match_tier TEXT, positive_repository TEXT, control_repository TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES study_evidence_assets(source_path));

CREATE TABLE study_rq2_c6_reproduced_tests(variable TEXT PRIMARY KEY REFERENCES study_rq2_c6_omnibus(variable), test_family TEXT NOT NULL, n_pairs INTEGER NOT NULL, calculated_p REAL NOT NULL, frozen_p REAL NOT NULL, tolerance_status TEXT NOT NULL, reproduction_record_json TEXT NOT NULL, verification_code_source_path TEXT NOT NULL REFERENCES study_evidence_assets(source_path));

CREATE TABLE study_rq2_c7_pathways(pair_index INTEGER PRIMARY KEY REFERENCES study_rq2_c6_pairs(pair_index), positive_case_id INTEGER NOT NULL, control_case_id INTEGER NOT NULL, positive_broad_pathway TEXT, original_row_json TEXT NOT NULL, source_path TEXT NOT NULL REFERENCES study_evidence_assets(source_path));

CREATE TABLE study_rq3_codeql_screen65_original(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),source_snapshot_type TEXT NOT NULL,
    generator_claim TEXT,scan_state TEXT NOT NULL,scanner_suite TEXT NOT NULL,
    before_total INTEGER,after_total INTEGER,new_strong INTEGER,new_weak INTEGER,
    historical_target_rules TEXT,new_rule_summary TEXT,
    summary_csv_sha256 TEXT NOT NULL,original_summary_row_json TEXT NOT NULL,
    result_source_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,result_zlib BLOB NOT NULL,
    link_to_generated_patch_status TEXT NOT NULL, functional_status TEXT NOT NULL);

CREATE TABLE study_rq3_owp14_original_artifacts(
      source_path TEXT PRIMARY KEY,case_id INTEGER,arm TEXT,
      source_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
      source_zlib BLOB NOT NULL,source_role TEXT NOT NULL);

CREATE TABLE study_rq3_owp14_original_transport(
    source_path TEXT PRIMARY KEY,condition_name TEXT NOT NULL,
    part_number INTEGER NOT NULL,sha256 TEXT NOT NULL,
    raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,status TEXT NOT NULL);

CREATE TABLE study_rq3_owp14_reproduction_checks(
      claim_key TEXT PRIMARY KEY,expected TEXT NOT NULL,observed TEXT NOT NULL,
      status TEXT NOT NULL,qualification TEXT NOT NULL);

CREATE TABLE study_rq3_owp14_run_scans(
      case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
      scan_state TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,codeql_version TEXT NOT NULL,
      historical_target_rule TEXT,new_strong_count INTEGER NOT NULL,new_conservative_count INTEGER NOT NULL,
      target_new_strong INTEGER NOT NULL,patch_sha256 TEXT NOT NULL,
      functional_status TEXT NOT NULL,baseline_codeql_version_match INTEGER,
      original_result_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,original_result_zlib BLOB NOT NULL,
      frozen_summary_row_json TEXT NOT NULL,patch_bytes_match_status TEXT NOT NULL,
      PRIMARY KEY(case_id,arm));

CREATE TABLE study_rq3_owp14_verified_archive(
     arm TEXT PRIMARY KEY CHECK(arm IN ('O','W','P')),original_zip_sha256 TEXT NOT NULL,
     source_fragment_paths_json TEXT NOT NULL,original_zip_bytes INTEGER NOT NULL,
     zip_zlib BLOB NOT NULL,verification_status TEXT NOT NULL);

CREATE TABLE study_rq3_owp14_verified_patch_bytes(
     case_id INTEGER NOT NULL,arm TEXT NOT NULL,original_filename TEXT NOT NULL,
     patch_sha256 TEXT NOT NULL,original_patch_bytes INTEGER NOT NULL,patch_zlib BLOB NOT NULL,
     patch_header_present INTEGER NOT NULL,verification_status TEXT NOT NULL,
     PRIMARY KEY(case_id,arm),
     FOREIGN KEY(case_id,arm) REFERENCES study_rq3_owp14_run_scans(case_id,arm),
     FOREIGN KEY(arm) REFERENCES study_rq3_owp14_verified_archive(arm));

CREATE TABLE study_rq3_t1_blind_pairs(pair_id TEXT PRIMARY KEY, blind_pair_decision TEXT NOT NULL, original_row_json TEXT NOT NULL, human_verified INTEGER NOT NULL DEFAULT 0);

CREATE TABLE study_rq3_t1_blind_sides(pair_id TEXT NOT NULL REFERENCES study_rq3_t1_blind_pairs(pair_id), blind_side TEXT NOT NULL, original_row_json TEXT NOT NULL, PRIMARY KEY(pair_id,blind_side));

CREATE TABLE study_rq_methodology_sources(
    source_path TEXT PRIMARY KEY, rq TEXT NOT NULL, role TEXT NOT NULL,
    sha256 TEXT NOT NULL,raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,
    integrity_status TEXT NOT NULL,human_verification TEXT NOT NULL);

CREATE TABLE study_rq_result_audit(
    claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,
    paper_or_archive_value TEXT NOT NULL,database_value TEXT,
    reproduce_sql TEXT,audit_status TEXT NOT NULL,
    caveat TEXT NOT NULL,audit_utc TEXT NOT NULL);

CREATE TABLE study_screen65_before_sarif_candidates_20261029 (
   case_id INTEGER NOT NULL REFERENCES cases(id),wave TEXT NOT NULL,zip_member_path TEXT NOT NULL UNIQUE,
   original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,sarif_version TEXT NOT NULL,
   tool_versions_json TEXT NOT NULL,scanner_run_count INTEGER NOT NULL,result_count INTEGER NOT NULL,
   comparability_status TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES study_sources(source_key),
   PRIMARY KEY(case_id,wave));

CREATE TABLE study_screen65_original_results_index(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    patch_key TEXT NOT NULL UNIQUE REFERENCES study_recovered_agent_patch_bytes(patch_key),
    source_status TEXT,source_notes TEXT,source_filename TEXT NOT NULL,
    original_row_json TEXT NOT NULL,
    provenance_scope TEXT NOT NULL DEFAULT 'UNVERIFIED_EXPERIMENT_INDEX_NOT_A_SCANNER_RESULT'
 );

CREATE TABLE study_seven_final_repair_archive(
      source_key TEXT PRIMARY KEY, original_path TEXT NOT NULL, original_sha256 TEXT NOT NULL,
      original_bytes INTEGER NOT NULL, source_zip_zlib BLOB NOT NULL,
      archive_index_zlib BLOB NOT NULL, start_here_zlib BLOB NOT NULL,
      component_digest_manifest_json TEXT NOT NULL,
      provenance_status TEXT NOT NULL);

CREATE TABLE study_seven_final_repair_case_evidence(
      case_id INTEGER PRIMARY KEY REFERENCES cases(id), final_patch_name TEXT NOT NULL,
      final_patch_sha256 TEXT NOT NULL, final_patch_zlib BLOB NOT NULL,
      final_result_name TEXT NOT NULL, final_result_sha256 TEXT NOT NULL, final_result_zlib BLOB NOT NULL,
      final_after_sarif_name TEXT NOT NULL, final_after_sarif_sha256 TEXT NOT NULL, final_after_sarif_zlib BLOB NOT NULL,
      initial_result_zlib BLOB, initial_before_sarif_zlib BLOB, initial_after_sarif_zlib BLOB,
      p1_initial_new_alert_count INTEGER NOT NULL, final_strong_new INTEGER NOT NULL,
      final_conservative_new INTEGER NOT NULL, final_scan_completed INTEGER NOT NULL,
      intervention_origin TEXT NOT NULL, functional_acceptance_status TEXT NOT NULL,
      causal_prevention_status TEXT NOT NULL, evidence_qualification TEXT NOT NULL,
      exact_source_archive_key TEXT NOT NULL REFERENCES study_seven_final_repair_archive(source_key));

CREATE TABLE study_sources(
  source_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, label TEXT NOT NULL, source_locator TEXT NOT NULL,
  source_sha256 TEXT, embedded_encoding TEXT, embedded_bytes BLOB, verification TEXT NOT NULL, notes TEXT
);

CREATE TABLE study_stage_ledger(
 stage_number INTEGER PRIMARY KEY, stage_name TEXT UNIQUE NOT NULL,
 status TEXT NOT NULL, detail TEXT, last_updated_utc TEXT NOT NULL
);

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

CREATE TABLE repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT UNIQUE NOT NULL,
    html_url TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    language TEXT,
    archived INTEGER DEFAULT 0,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_policy(policy_key TEXT PRIMARY KEY,rule TEXT NOT NULL);

CREATE TABLE review_table_catalog(table_name TEXT PRIMARY KEY,domain TEXT NOT NULL,purpose TEXT NOT NULL,lifecycle TEXT NOT NULL,source_row_count INTEGER NOT NULL,notes TEXT NOT NULL);

CREATE TABLE review_column_catalog(table_name TEXT NOT NULL,column_name TEXT NOT NULL,data_type TEXT,declared_not_null INTEGER,pk_position INTEGER,default_sql TEXT,notes TEXT NOT NULL,PRIMARY KEY(table_name,column_name));

CREATE TABLE review_relationship_catalog(child_table TEXT NOT NULL,foreign_key_id INTEGER NOT NULL,column_sequence INTEGER NOT NULL,child_column TEXT,parent_table TEXT,parent_column TEXT,on_update_action TEXT,on_delete_action TEXT,PRIMARY KEY(child_table,foreign_key_id,column_sequence));

CREATE TABLE review_run_catalog(run_id TEXT PRIMARY KEY REFERENCES study_experiment_runs(run_id),evidence_class TEXT NOT NULL,selection_policy TEXT NOT NULL,classification_basis TEXT NOT NULL,classification_evidence_json TEXT NOT NULL,functional_validity TEXT NOT NULL,independent_generation_attestation TEXT NOT NULL);

CREATE TABLE review_claim_history(evidence_id TEXT PRIMARY KEY,source_table TEXT NOT NULL,source_key TEXT NOT NULL,claim_key TEXT NOT NULL,rq TEXT,status TEXT,statement TEXT,caveat TEXT,explicit_correction INTEGER NOT NULL);

CREATE TABLE review_quality_issues(issue_id TEXT PRIMARY KEY,severity TEXT NOT NULL,entity_type TEXT NOT NULL,entity_key TEXT NOT NULL,issue TEXT NOT NULL,interpretation TEXT NOT NULL);

CREATE TABLE review_artifact_index(artifact_key TEXT PRIMARY KEY,source_table TEXT NOT NULL,source_pk_json TEXT NOT NULL,case_id INTEGER,run_id TEXT,role TEXT NOT NULL,sha256 TEXT,original_bytes INTEGER,embedded INTEGER NOT NULL,payload_column TEXT,encoding TEXT NOT NULL,source_locator TEXT,association_basis TEXT NOT NULL);

CREATE INDEX study_imported_artifacts_case_role ON study_imported_evidence_objects(case_id,role);

CREATE INDEX study_imported_f_rule_case ON study_imported_codeql_findings(case_id,rule_id,new_vs_baseline);

CREATE INDEX study_imported_f_run_new ON study_imported_codeql_findings(run_id,new_vs_baseline);

CREATE INDEX study_imported_m_case_method ON study_imported_codeql_metrics(case_id,method);

CREATE INDEX idx_cases_status ON cases(status);

CREATE INDEX review_artifact_case ON review_artifact_index(case_id);

CREATE INDEX review_artifact_run ON review_artifact_index(run_id);

CREATE VIEW review_v_cases AS SELECT c.id AS case_id,c.repo_id,c.issue_id,c.pr_id,c.ai_cohort,c.status AS mining_status,c.final_label AS mining_label,
       EXISTS(SELECT 1 FROM study_classifications a WHERE a.case_id=c.id) AS in_original122,
       EXISTS(SELECT 1 FROM study_new70_context_frozen n WHERE n.case_id=c.id) AS in_new70,
       (SELECT COUNT(*) FROM study_experiment_runs r WHERE r.case_id=c.id) AS experiment_runs FROM cases c;

CREATE VIEW review_v_original122 AS SELECT * FROM study_classifications;

CREATE VIEW review_v_annotation_history AS SELECT * FROM study_annotation_events;

CREATE VIEW review_v_new70_final_findings AS SELECT * FROM study_new70_final_findings;

CREATE VIEW review_v_new70_preliminary_candidates AS SELECT * FROM study_new70_canonical_prelim_254;

CREATE VIEW review_v_producing_changes AS SELECT * FROM study_frozen_broad_attribution;

CREATE VIEW review_v_final_root_coding AS SELECT * FROM study_d7_final_roots_342;

CREATE VIEW review_v_matched_pairs AS SELECT * FROM study_matched_control_pairs_C2;

CREATE VIEW review_v_reproduced_statistics AS SELECT * FROM study_rq2_c6_reproduced_tests;

CREATE VIEW review_v_runs AS SELECT r.run_id,r.case_id,r.root_id,r.experiment_family,r.treatment,r.status AS source_status,
       p.evidence_class,p.selection_policy,p.classification_basis,p.functional_validity,p.independent_generation_attestation,
       CASE WHEN r.prompt_blob IS NOT NULL THEN 'MAIN_FIELD_PRESENT' WHEN EXISTS(SELECT 1 FROM study_imported_evidence_objects e WHERE e.run_id=r.run_id AND e.role='self_written_prompt' AND e.content_zlib IS NOT NULL) THEN 'SELF_WRITTEN_PROMPT_ARTIFACT_PRESENT_INVOCATION_UNVERIFIED' ELSE 'MAIN_FIELD_EMPTY_CHECK_ARCHIVED_INPUT_PACKETS' END AS prompt_status,
       (SELECT COUNT(*) FROM study_generated_patches g WHERE g.run_id=r.run_id) AS patch_count,
       (SELECT COUNT(*) FROM study_experiment_scans s WHERE s.run_id=r.run_id) AS scan_count,
       (SELECT COUNT(*) FROM review_artifact_index a WHERE a.run_id=r.run_id) AS indexed_artifact_count
       FROM study_experiment_runs r JOIN review_run_catalog p USING(run_id);

CREATE VIEW review_v_archived_owp_runs AS SELECT * FROM review_v_runs WHERE evidence_class='ARCHIVED_ORIGINAL_OWP';

CREATE VIEW review_v_later_exploratory_runs AS SELECT * FROM review_v_runs WHERE selection_policy='SUPPLEMENTARY_ONLY';

CREATE VIEW review_v_patches AS SELECT p.patch_id,p.run_id,r.case_id,r.evidence_class,p.content_sha256,p.authenticity_status,
       p.patch_blob IS NOT NULL AS embedded,p.patch_uri,p.notes FROM study_generated_patches p LEFT JOIN review_v_runs r USING(run_id);

CREATE VIEW review_v_scans AS SELECT s.scan_id,s.run_id,r.case_id,r.evidence_class,s.scanner,s.scanner_version,s.rule_id,s.execution_verified,
       s.raw_result_blob IS NOT NULL AS raw_result_embedded,r.functional_validity FROM study_experiment_scans s LEFT JOIN review_v_runs r USING(run_id);

CREATE VIEW review_v_claims_current AS SELECT a.claim_id,a.rq,a.paper_or_archive_value,a.database_value,a.reproduce_sql,
       a.audit_status AS historical_audit_status,COALESCE(s.current_evidence_status,a.audit_status) AS documented_current_status,
       CASE WHEN s.claim_id IS NOT NULL THEN 'EXPLICIT_CLAIM_ID_SUPERSESSION' ELSE 'HISTORICAL_AUDIT_NO_EXPLICIT_SUPERSESSION' END AS resolution_rule,
       a.caveat AS historical_caveat,COALESCE(s.caveat,a.caveat) AS current_caveat,s.evidence,s.source_key
       FROM study_rq_result_audit a LEFT JOIN study_claim_status_supersession_20261029 s USING(claim_id)
       UNION ALL SELECT s.claim_id,s.rq,NULL,NULL,NULL,NULL,s.current_evidence_status,'EXPLICIT_SUPERSESSION_ADDITIONAL_CLAIM',NULL,s.caveat,s.evidence,s.source_key
       FROM study_claim_status_supersession_20261029 s LEFT JOIN study_rq_result_audit a USING(claim_id) WHERE a.claim_id IS NULL;

CREATE VIEW review_v_claim_evidence_history AS SELECT * FROM review_claim_history;

CREATE VIEW review_v_artifacts AS SELECT * FROM review_artifact_index;

CREATE VIEW review_v_quality_issues AS SELECT * FROM review_quality_issues;