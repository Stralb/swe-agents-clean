# Archived OSV snapshot execution — synthetic local Git and fake CLI

The helper `tests/support/archived_osv_local_process.py` compiles the exact archived `scan_dependency_snapshots`, `_discover_dependency_companions`, `_materialize_git_snapshot`, `_scan_dir` and associated pure functions from SHA-256 `4dda6859dbbf95af17bb43633cc2bdc8335bb12ec766d520cbbe5c9ea3f46834`. It never imports or edits the original scanner module. It uses the SHA-pinned original shell helper.

A local two-commit fixture changes `fixture/pyproject.toml` while leaving `fixture/poetry.lock` unchanged. The historical Git clone (only) is redirected from the fixed `example.invalid` URL to the self-generated `file://` repository. The exact original `git fetch`, `git ls-tree`, `git show` and snapshot materialization calls then reconstruct both states, including the unchanged companion lockfile.

A generated executable **named** `osv-scanner` is **not OSV** and has no advisory engine. It validates that the two synthetic manifests and companion lockfile were materialized correctly and prints a fabricated, OSV-shaped JSON report. The head reports one `OSV-SYNTHETIC-0001` advisory; the base reports none. The original code filters to the novel advisory family and returns an introduced dependency result with before/head metadata. An additional test uses the exact original worker dispatcher and `scan_case` to persist the result to original SQLite tables inside `disposable_original_database()`.

The helper permits only approved git commands, SHA values, files and one synthetic repo identity, and does not contact GitHub, Wits or any real repository. It cannot prove OSV's detection behavior, actual historical advisory DB contents, original pinned scanner version, or the frozen 3,809-cohort results. Actual OSV executable/DB acquisition and network-disabled genuine-binary testing remain open.

Run `python -m unittest tests.test_miner_archived_osv_local_process -v` or the full suite.


## Historical malformed-report contract

The original `_scan_dir` treats a zero-exit CLI as `status=ok` even if `parse_json_maybe(stdout)` does **not** produce a dict. That can create a misleading success with an empty finding list. Conversely, a parseable report containing structured findings but whose stderr contains `could not extract` is marked `parse_failed` while retaining the structured findings. Dedicated synthetic failure-mode tests exercise the exact unchanged code. Their outcomes must be separated from scientific negative examples; original stdout, stderr, exit codes and data hashes are needed to determine whether the historical run suffered from these conditions.
