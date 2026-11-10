SELECT * FROM cases_and_warnings WHERE case_id=3375;
SELECT * FROM experiment_to_scanner ORDER BY case_id,run_id;
SELECT * FROM human_vs_reference WHERE verdict_status IS NOT NULL;
SELECT * FROM owp_historical_results ORDER BY case_id,condition;
SELECT * FROM scientific_limitations ORDER BY severity;
