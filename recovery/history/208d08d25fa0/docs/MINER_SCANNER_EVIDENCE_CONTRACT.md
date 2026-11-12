# Historical scanner evidence and job-state bridge (test-only)

## Scope

**Original historical functions, synthetic input only.** The recovered `src/scanners/scanner_runner.py` has SHA-256 `f2507c1d487aebf8e9bd69cad8ff4c7315e781dbe8328cfaed423c2c3ace070f` in all three miner snapshots. The historical file is unchanged. `tests/support/archived_scanner_records_contract.py` checksum-verifies it before compiling only `_insert_run`, `_insert_finding`, `_scanner_already_ran`, `_clear_scanner` and `_codeql_finding_type` into a test-only namespace. It does not import the historical scanner runner or give access to `scan_case`/scanner binaries.

`tests/support/archived_job_queue_contract.py` now also exposes the original `_job_status_from_runs`, `_job_status_from_scanner_runs`, and `sync_jobs_from_scanner_runs`. These functions are still bound to disposable SQLite. The original active case-stage modules remain byte-for-byte preserved.

## Confirmed original behaviours (synthetic contract tests)

1. `_insert_run()` truncates standard output and error output to their last 5,000 characters unless `preserve_full=True`.
2. `_insert_finding()` serializes dictionary evidence and raw JSON, retains raw strings, picks rule identifiers from `rule` / `rule_id` / `vuln_id`, and defaults `introduced=1`.
3. `_scanner_already_ran()` checks **existence**, not success: a previous `tool_missing` or `error` run also counts as already run.
4. `_codeql_finding_type()` treats only a non-whitespace CWE field as a vulnerability. Other CodeQL findings are `code_quality`.
5. `_clear_scanner()` deletes findings by *finding type* rather than scanner ownership. Under a CodeQL cleanup, a Semgrep `vulnerability` finding is also deleted, although its Semgrep scanner run remains. **This is a potential cross-scanner evidence-loss mechanism in the unchanged historical implementation.**
6. `sync_case_statuses()` counts all introduced findings regardless of `finding_type`. A standalone introduced CodeQL `code_quality` finding produces case status `needs_review` and downstream signal `vulnerability`, even though it is *not* a vulnerability under `_codeql_finding_type()`. **This is a classification mismatch**, not verified prevalence in historical cases.
7. Synthetic `scanner_runs` for Semgrep, Gitleaks, dependency-diff, OSV, Trivy and CodeQL can update all six original `scanner_jobs` without executing tools, leading to `scanned_clean`; a recorded scanner error blocks that job while other pending jobs keep the case running.

## Reproducibility and limitations

These findings describe directly tested, exact source behaviour under synthetic data—not a re-evaluation of real mined cases, and **not evidence that either defect changed the study's reported counts**. The direct original scanner execution and all external dependencies (CodeQL, Semgrep, Gitleaks, OSV, Trivy, clones, shell, Slurm) remain disconnected. The copied historical runner is never an active production module.

Rerun: `python -m unittest tests.test_miner_scanner_evidence_contract -v` or `python -m unittest discover -s tests -v`.
