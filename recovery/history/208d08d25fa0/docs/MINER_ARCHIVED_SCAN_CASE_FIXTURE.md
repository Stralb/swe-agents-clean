# Exact archived scan_case orchestration — all six synthetic scanner branches

## Executed source and safety

The test harness `tests/support/archived_fixture_scan_case.py` executes the original SHA-256-pinned `scan_case()` AST definition from `historical/miner/2026-10-20-live-export/src/scanners/scanner_runner.py`. This historical file is not imported or edited. The harness injects **synthetic-only** backends for all six branches: Gitleaks, dependency-diff, OSV, Trivy, Semgrep and CodeQL. No scanner library is imported from the archived miner, no GitHub client is instantiated, and no subprocess or external scanner is invoked.

All persistence goes through the original `_insert_run`, `_insert_finding`, `_scanner_already_ran`, `_clear_scanner` and `_codeql_finding_type` functions against a newly created `disposable_original_database()`. CodeQL's exact original pure language/diff/added-line functions are also injected. All six scanner flags must be specified as literal booleans. Each requested scan that needs a backend requires a supplied fixture; absent or malformed fixtures raise `MissingScannerFixture(BaseException)` rather than being mistaken for a clean scan. Snapshot URLs are limited to `https://example.invalid/`. Case/PR identity must already exist in the disposable DB.

Each OSV and Trivy fixture has exactly four items: findings, summary metadata, base metadata and head metadata. Semgrep and Gitleaks fixtures have two items: findings and metadata. Dependency-diff fixtures are explicit lists of regression findings; a **clean** synthetic result must be supplied as `[]`, not omitted. CodeQL fixtures are explicitly mapped by snapshot SHA.

## What the contract tests establish

- The unchanged Gitleaks path records and caches synthetic secret findings; a force-rescan replaces earlier secret evidence.
- The unchanged CodeQL path executes both snapshot branches, preserves language-specific and aggregate run records, finds introduced results and applies original PR-added-line filtering; missing diff patches can prevent promotion.
- The unchanged dependency-diff path records synthetic regressions as `dependency` findings and marks a non-dependency PR with no regression as `not_applicable`. Its `ok` status is not evidence of scanner-binary execution.
- The unchanged OSV and Trivy paths preserve synthetic base/head/aggregate statuses, stdout/stderr persistence and dependency finding serialization. Their snapshot-specific output is stored without the ordinary 5,000-character truncation; aggregate output is truncated by the original `_insert_run`.
- The unchanged Semgrep path records synthetic `vulnerability` findings by default while respecting explicitly supplied finding types; configuration, timeout and missing-snapshot behavior are observable.
- The original cache skips already-recorded runs based on **existence even after failure**. The two dependency scanners' force-rescan code deletes only their own findings, but dependency-diff force-rescan uses `_clear_scanner(..., ("dependency",))` and deletes **other scanners' dependency findings** too. Original CodeQL cleanup can similarly delete Semgrep vulnerability evidence. These are retained historical behaviors, **not repaired or used as empirical prevalence estimates**.
- The original OSV/Trivy/Semgrep branches insert returned findings even when their aggregate metadata reports an error. Tests distinguish persisted evidence from a successful scan.
- A single fixture-only collector → queue → Gitleaks handoff and an all-six-scanner disposable-DB scan/queue bridge exercise the original data shape without accessing historical production data.

## Boundaries and reproducibility

These tests replay original orchestration **against synthetic provider responses**. They neither show that a real vulnerability exists nor reproduce any frozen scanner count. Missing original manifests, scanner versions and CodeQL query packs still block real-world parity. No repo cloning, external network, scanner binary, GitHub mutation outside this private work branch, Wits access or Slurm activity occurred.

The original scanner, queue and database archival bytes stay unchanged; known failings are documented rather than silently fixed. See `docs/MINER_SCANNER_EVIDENCE_CONTRACT.md` for case status / cross-scanner evidence warnings.

Run: `python -m unittest tests.test_miner_archived_fixture_scan_case tests.test_miner_archived_fixture_other_scanners -v` or `python -m unittest discover -s tests -v`.
