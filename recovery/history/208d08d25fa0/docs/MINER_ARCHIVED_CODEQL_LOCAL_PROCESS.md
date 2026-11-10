# Original archived CodeQL Git and SARIF runner — synthetic local process

The SHA-256 verified historical scanner `codeql_scanner.py` (`03bad76387b998d3b8978299cc9322a3a7a792c6e46fa4ce7338c4808fd6f198`) is unchanged. `tests/support/archived_codeql_local_process.py` extracts only a fixed AST function inventory, preserving the original `scan_snapshot_with_codeql`, `_codeql_tempdir`, `_codeql_preflight`, Git clone/fetch/checkout, CodeQL `database create` and `database analyze` argument construction, SARIF interpretation and original failure metadata. The archived shell runner is separately SHA-pinned.

The helper generates a two-commit local Git repo containing only a harmless Python function. The one historical `git clone` URL is redirected to a self-generated `file://` repository. All command arguments, target SHAs, output paths and CodeQL suite names are allowlisted. A local deterministic executable named `codeql` emits a synthetic SARIF warning with fabricated CWE metadata on an added line. **It is not CodeQL.** No real target or Wits data is accessed.

Five normal test contracts assert (1) unchanged archived clone→checkout→database→SARIF parsing; (2) rejection of nonfixture repo/SHAs/query suites; (3) original `no_source` status; (4) original malformed SARIF returns `status=ok` with zero findings; and (5) exact archived `run_scanner_job` → `scan_case` → base/head SARIF differencing → PR added-line linking → CWE-tagged `scanner_findings` → disposable original SQLite and case stage.

**Research caveats:** The original matching key omits CWE and line, missing patches suppress attribution, and CodeQL statuses `no_source` and `ok` are both accepted by original `scan_case` for differencing. Source-level reproduction of these mechanisms does not measure historical prevalence. The genuine CodeQL engine, query suite version and historical SARIF baselines are separate gates. Never treat a fake SARIF marker as a real vulnerability.

Run `python -m unittest tests.test_miner_archived_codeql_local_process -v`.


## Malformed SARIF regression

A test-only CLI mode returns exit code zero after writing `NOT VALID SARIF JSON` for the fabricated head. The exact archived `scan_snapshot_with_codeql()` accepts this as `status=ok` with no findings. This is preserved as **original fail-open behavior**, never treated as evidence that the PR is clean or a security improvement. No historical SARIF case prevalence is inferred from the synthetic test.
