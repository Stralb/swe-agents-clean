-- Reviewer-friendly run -> patch -> scanner result lookup
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
