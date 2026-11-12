README = '''# Arno research reviewer edition

This is a lossless, structured edition of the preserved research master. Start with
`ARNO_RESEARCH_MASTER_REVIEW.sqlite`, the CSV indexes in `tables/`, and
`REPRODUCE.sql`. SQLite is the only database dependency.

## What changed

All 127 original tables (including SQLite's sequence table) and their records are
preserved. New `review_*` catalogs and `review_v_*` views provide navigation.
No original experiment, annotation, status or payload was overwritten. The smaller
evidence vault is already embedded in the master and need not be uploaded again.
This edition is derived from the immutable snapshot that previously passed the
full SQLite integrity check, verified by its SHA-256 while copying.

## Which evidence takes precedence

Later is not automatically truer. A documented correction applies to the exact
claim it explicitly supersedes; both versions remain visible. Later exploratory
tests never replace missing historical runs. Recovered original bytes establish
preservation, not correctness, independent human review or agent authenticity.

Use `review_v_claims_current` for the explicit claim-audit/supersession overlay,
and `review_v_claim_evidence_history` for all recorded readiness statements.
Other audit families are preserved independently: similar wording or dates are
not enough to assert that one supersedes another. Old stage-ledger and pending
flags are historical; they can conflict with later recovered final tables.
The displayed current status is documented source status, not a new validation.

## Read the data in this order

1. `review_v_cases`: the original 3,809-case issue/PR registry.
2. RQ1: `review_v_original122`, `review_v_new70_final_findings`,
   `review_v_producing_changes`, `review_v_final_root_coding`.
3. RQ2: `review_v_matched_pairs`, `review_v_reproduced_statistics`.
4. RQ3: `review_v_runs`, `review_v_archived_owp_runs`,
   `review_v_later_exploratory_runs`, `review_v_patches`, `review_v_scans`.
5. `review_v_artifacts`, `review_v_quality_issues` and the complete dictionaries.

## Original versus later experiments

| Class | Interpretation |
| --- | --- |
| ARCHIVED_ORIGINAL_OWP | Original 40 archived O/W/P scanner conditions; candidate historical evidence, not newly rerun or functionally validated here. |
| LATER_NONBLIND_NEW_O | Two new non-blind O generations. They do not fill the missing original O arms. |
| LATER_ANALYSIS_OF_HISTORICAL_PATCH | Later scanner analysis of historical P1 patches; not the historical scanner invocation. |
| LATER_BASELINE_SCAN | Baseline scans within the later architectural experiment family. |
| LATER_ARCHITECTURAL_EXPERIMENT | Separate architectural, SCGG and self-prompt generation experiments; supplementary by default. |
| UNRESOLVED_ORIGIN | No explicit origin rule matched; excluded pending inspection. |

These are evidence-navigation classes, not findings that an experiment is valid
or invalid. No run is silently selected as a publication's primary analysis.
Use the preserved protocol, source snapshots, treatment and validity qualifications
to define any analysis. Never combine later reruns with original arms as if paired.

## Identifiers, missingness and units

- `case_id` identifies an issue/PR case; `run_id` identifies an experiment.
- Producing-change IDs require `cohort`; preliminary/final canonical IDs are
  distinct versions. Do not merge them by bare ID.
- Findings, producing changes, root decisions, cases and runs are different units.
- NULL/blank prompts mean unavailable in the main field, not necessarily absent
  from archived packets. A self-written prompt is not a complete invocation trace.
- Source locators may refer to original cluster paths. Prefer embedded payloads
  and hashes. Unresolved links remain explicit rather than invented.
- Scanner alerts are not independently confirmed exploitable vulnerabilities.
- Human adjudication, generator identity, functional equivalence and causal
  prevention remain qualified exactly as the source evidence records them.

## Files and tools

- `tables/table_catalog.csv`: every original table, its domain and row count.
- `tables/column_catalog.csv`: original column types, keys, defaults and cautions.
- `tables/relationships.csv`: declared foreign-key relationships.
- `tables/runs.csv`: evidence classes and run qualifications.
- `tables/current_claims.csv`: original and explicitly superseding claim statuses.
- `tables/claim_history.csv`: uncollapsed status evidence across audit families.
- `tables/artifacts.csv`: explicit case/run links, payload locations and encodings.
- `tables/quality_issues.csv`: remaining gaps and broken declared references.
- `REPRODUCE.sql`: descriptive counts with distinct denominators; not a full replay.
- `artifact_reader.py`: extract an indexed payload into a NEW file with checksum
  validation where available. This does not execute archived code.
- `VALIDATION.json`: copy hash, preserved table counts and view checks.
- `MANIFEST.json` and `SHA256SUMS`: final edition checksum and provenance.

Example:

```sh
sqlite3 -header -csv ARNO_RESEARCH_MASTER_REVIEW.sqlite < REPRODUCE.sql
python3 artifact_reader.py list --case 3429
python3 artifact_reader.py list --run OWP14_CASE03429_O
```

Keep this database private. Preservation was not a separate disclosure/redaction
review. This release does not certify export of the entire ChatGPT project.
'''


QUERIES = '''-- Descriptive counts only. Every query states its analysis unit.
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
'''

