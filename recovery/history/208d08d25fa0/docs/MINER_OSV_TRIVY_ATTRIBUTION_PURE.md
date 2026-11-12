# Exact archived OSV and Trivy attribution helpers: offline-only

## Source and function boundaries

The three August/October recovered scanner snapshots agree byte-for-byte:

| Scanner | SHA-256 | Original Git blob |
| --- | --- | --- |
| OSV | `4dda6859dbbf95af17bb43633cc2bdc8335bb12ec766d520cbbe5c9ea3f46834` | `a8165193667a83432193d2837fffe09dd2cbcb1e` |
| Trivy | `e8e18cf902611d2c56f4bc993ea3d0465e34dbbee6af401c395fc44dd89d4620` | `c69352db35c89005e0402640630e16fb3d78695f` |

`tests/support/archived_dependency_snapshot_pure.py` verifies these exact SHA-256 source bytes and selectively compiles only function definitions without decorators/import-time behavior. It does **not import** the archived scanner modules, initialize scan clients, run OSV/Trivy executables, clone Git repositories, or supply `run_cmd`. The exact original `is_dependency_file` comes from the byte-identically promoted `src.scanners.dependency_diff` module, with candidate `packaging==25.0` under a SHA-pinned wheel in CI.

## Tested attribution contracts

- OSV base/head dependency-path selection, added/removed/renamed files, rename aliases, associated advisory identifiers, path normalization and severity/timeout status precedence.
- Original OSV `_snapshot_finding_key` compares the **whole sorted advisory-ID tuple**. If a previously present vulnerability loses one alias between snapshots, its before/after keys can differ despite sharing another advisory ID. Tests demonstrate this as a source-level classification risk, **not observed cohort prevalence**.
- Trivy `_snapshot_delta_findings` instead checks for **overlapping advisory identifiers** at the same finding locator. The pure `_introduced_findings` then requires a changed dependency target and annotates the result with original `pr_attributable` evidence.
- If Trivy advisory IDs are missing, exact original matching does not establish pre-existence; a superficially identical synthetic alert can be retained as a new snapshot delta. Trivy suffix path matching can be broad and its `lstrip("./")` normalizer removes leading dot prefixes; these are historical semantics, not fixes.
- Original status aggregation differs: OSV prioritizes `error` over `timeout` and returns `ok` for two `not_applicable` statuses; Trivy prioritizes `timeout` over `error` and preserves all-`not_applicable`. These differences must be considered in scanner/job-status reconciliation.
- A synthetic result produced by the **exact original Trivy pure attribution** is passed through the already-audited historical `scan_case` branch into disposable original SQLite, verifying preservation of scanner identity and evidence serialization without using an OSV/Trivy binary.

## Release gate / interpretation

This is the original **attribution and evidence-shaping logic only**, not original end-to-end `scan_dependency_snapshots` or `scan_dependency_snapshots_with_trivy` execution. Their external Git checkout, scanner invocation, advisory database/source snapshots, and environmental state remain disconnected. No actual historical alert difference or vulnerability count can be inferred from these tests.

Rerun `python -m unittest tests.test_miner_osv_trivy_attribution_pure -v` or the full suite.
