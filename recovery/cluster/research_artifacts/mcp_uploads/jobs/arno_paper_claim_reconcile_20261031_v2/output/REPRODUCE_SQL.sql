-- Run in read-only mode on ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite
SELECT COUNT(*) cases,COUNT(DISTINCT repo_id) repos FROM cases;
SELECT collection_phase,COUNT(*) FROM study_cases GROUP BY collection_phase;
SELECT mapping_status,COUNT(*) FROM study_findings GROUP BY mapping_status;
SELECT attribution,COUNT(*) FROM study_producing_changes GROUP BY attribution;
SELECT route,COUNT(*) FROM study_roots GROUP BY route;
SELECT COUNT(*) pairs,SUM(same_repository) same_repo FROM arno_matched_control_pairs_C2;
WITH x AS (SELECT case_id,MAX(CASE WHEN arm='O' THEN new_strong_count END) O,
MAX(CASE WHEN arm='W' THEN new_strong_count END) W,
MAX(CASE WHEN arm='P' THEN new_strong_count END) P
FROM arno_rq3_owp14_run_scans GROUP BY case_id HAVING COUNT(DISTINCT arm)=3)
SELECT COUNT(*) triples,SUM(O) O_total,SUM(W) W_total,SUM(P) P_total,
SUM(W<O) W_improved,SUM(P<O) P_improved FROM x;
SELECT status,COUNT(*) FROM study_human_reviews GROUP BY status;
