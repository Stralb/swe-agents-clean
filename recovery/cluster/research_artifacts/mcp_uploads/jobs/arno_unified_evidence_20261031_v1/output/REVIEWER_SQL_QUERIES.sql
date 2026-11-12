-- The new DB is RESTRICTED; raw source evidence includes uncontrolled third-party code.
SELECT collection_phase,COUNT(*) cases FROM study_cases GROUP BY collection_phase;
SELECT count(*) findings FROM study_findings;
SELECT mapping_status,count(*) n FROM study_findings GROUP BY mapping_status;
SELECT attribution,count(*) n FROM study_producing_changes GROUP BY attribution;
SELECT experimental_family,count(*) n,SUM(patch_embedded) patches,SUM(raw_scan_embedded) raw_scans FROM study_runs GROUP BY experimental_family;
SELECT * FROM study_paper_findings WHERE case_id=3429;
SELECT * FROM study_paper_human_reviews;
SELECT * FROM study_limitations;
