# Exact archived Trivy snapshot driver — synthetic Git and fake CLI

## Why this matters

Earlier offline tests exercised the unchanged pure Trivy advisory and PR-attribution methods with fabricated scanner responses. This stage additionally executes the **exact original top-level `scan_dependency_snapshots_with_trivy` and `_scan_snapshot` AST functions**: original Git clone/fetch, base/head worktree creation, Trivy CLI command construction, JSON report parsing, package-location attachment, advisory delta and changed-target attribution. The historical module is SHA-verified (`e8e18cf902611d2c56f4bc993ea3d0465e34dbbee6af401c395fc44dd89d4620`) and is **not imported as a module or modified**.

The test-only helper `tests/support/archived_trivy_local_process.py` generates a local two-commit repository. Base manifest is `synthetic-lib==2.0`; head is `synthetic-lib==1.0`. A temporary executable named `trivy` is **not a real scanner**; it returns a deterministic fabricated alert (`SYNTHETIC-TRIVY-0001`) only for the head manifest. The wrapper intercepts the one historical clone URL and redirects it to the local generated `file://` fixture. Every subprocess command, clone/fetch SHA, worktree target, fake executable and diff payload is explicitly validated. The only network-style name accepted is `https://example.invalid/fixture/trivy-snapshots`, which is never contacted.

Original worker queue, `scan_case`, `scanner_runs`, `scanner_findings` and case-status functions are then exercised against `disposable_original_database()`, proving the resulting synthetic advisory becomes an introduced dependency finding requiring review.

## Verification and caveats

This proves **original shell/Git/JSON/data persistence wiring**, *not* Trivy binary execution or its actual vulnerability-database rules. Neither historical alert counts nor the archived Trivy advisory feed have been independently reproduced. The fake executable contains no advisories except a deliberately fabricated one. Do not run this fixture on real targets; do not reuse it to label historical cases. Exact external executable version, offline DB hash, source snapshot, original SQL and case-level parity are still required.

Run `python -m unittest tests.test_miner_archived_trivy_local_process -v` (or full suite).


## Historical malformed-report contract

The original `_scan_snapshot` returns `parse_failed` when a zero-exit scanner produces invalid JSON, but if a valid JSON report exists, the `status` depends on whether report targets were emitted, **not** on process exit success. A deliberately nonzero synthetic CLI exit with a structured report can therefore be marked `ok`. Dedicated failure-mode tests exercise this unchanged source behavior; it is not evidence that any historical warning was incorrectly attributed. Preserve original process exit codes and report bytes before comparing scanner-positive cohorts.
