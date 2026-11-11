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
