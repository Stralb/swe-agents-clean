-- Descriptive counts only. Every query states its analysis unit.
SELECT 'mined_cases' AS unit,COUNT(*) AS n FROM review_v_cases;
SELECT 'original122_annotations' AS unit,COUNT(*) AS n FROM review_v_original122;
SELECT 'final_new70_findings' AS unit,COUNT(*) AS n FROM review_v_new70_final_findings;
SELECT 'preliminary_new70_candidates_NOT_FINAL' AS unit,COUNT(*) AS n FROM review_v_new70_preliminary_candidates;
SELECT 'producing_changes' AS unit,cohort,COUNT(*) AS n FROM review_v_producing_changes GROUP BY cohort;
SELECT 'final_roots' AS unit,final_route,COUNT(*) AS n FROM review_v_final_root_coding GROUP BY final_route;
SELECT 'matched_pairs' AS unit,COUNT(*) AS n FROM review_v_matched_pairs;
SELECT 'recorded_statistical_reproductions' AS unit,COUNT(*) AS n FROM review_v_reproduced_statistics;
SELECT 'runs' AS unit,evidence_class,selection_policy,COUNT(*) AS n FROM review_v_runs GROUP BY evidence_class,selection_policy;
-- Expect 40 historical arms across 14 cases, with only 12 complete O/W/P triples.
SELECT COUNT(*) AS historical_arms,COUNT(DISTINCT case_id) AS historical_cases FROM review_v_archived_owp_runs;
SELECT COUNT(*) AS complete_original_triples FROM (SELECT case_id FROM review_v_archived_owp_runs GROUP BY case_id HAVING COUNT(DISTINCT treatment)=3);
SELECT 'later_nonblind_O_NOT_historical_recovery' AS unit,COUNT(*) AS n FROM review_v_runs WHERE evidence_class='LATER_NONBLIND_NEW_O';
SELECT 'prompt_field_and_linked_prompt_availability' AS unit,prompt_status,COUNT(*) AS n FROM review_v_runs GROUP BY prompt_status;
SELECT 'scans' AS unit,evidence_class,execution_verified,COUNT(*) AS n FROM review_v_scans GROUP BY evidence_class,execution_verified;
SELECT claim_id,historical_audit_status,documented_current_status,resolution_rule,current_caveat FROM review_v_claims_current ORDER BY claim_id;
SELECT severity,issue,COUNT(*) AS n FROM review_v_quality_issues GROUP BY severity,issue;
-- For a manuscript claim, inspect reproduce_sql in review_v_claims_current;
-- those archived SQL strings have NOT automatically been executed here.

-- Read-only walkthrough: original experiments and later tests for case 3429.
-- Date alone does not make a later run the replacement for an original run.
SELECT run_id,evidence_class,treatment,source_status,prompt_status,patch_count,scan_count
FROM review_v_runs WHERE case_id=3429 ORDER BY evidence_class,run_id;

SELECT patch_id,run_id,evidence_class,content_sha256,authenticity_status,embedded
FROM review_v_patches WHERE case_id=3429 ORDER BY run_id,patch_id;

SELECT scan_id,run_id,evidence_class,scanner,scanner_version,execution_verified,functional_validity
FROM review_v_scans WHERE case_id=3429 ORDER BY run_id,scan_id;

SELECT artifact_key,run_id,role,sha256,embedded,encoding,source_table,payload_column
FROM review_v_artifacts WHERE case_id=3429 ORDER BY run_id,role,artifact_key;
