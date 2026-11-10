-- Run read-only on V2 database.
SELECT registration_source,experiment_family,condition,COUNT(*) runs FROM study_all_experimental_runs
 GROUP BY registration_source,experiment_family,condition;
SELECT condition,COUNT(*) runs,SUM(new_warnings) new_scanner_alerts
 FROM study_deep_runs WHERE cohort_name='RPL7_RETROSPECTIVE_ORACLE' GROUP BY condition;
SELECT condition,COUNT(*) runs,SUM(new_warnings) new_scanner_alerts
 FROM study_deep_runs WHERE cohort_name='AC6_EXPLORATORY_NONRANDOMIZED' GROUP BY condition;
SELECT COUNT(*) FROM study_deep_input_packages;
SELECT COUNT(*) FROM study_deep_vault_patch_index;
SELECT count(*) FROM study_deep_evidence WHERE role IN ('patch','after_sarif');
SELECT pilot_condition,output_generation_status FROM study_deep_pilot_inputs;
-- Warning counts are not exploitability or functional correctness measures.
