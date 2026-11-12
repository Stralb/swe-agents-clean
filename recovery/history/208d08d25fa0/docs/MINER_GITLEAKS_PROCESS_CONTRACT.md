# Gitleaks process-boundary contract (local synthetic executable)

This milestone goes deeper than returning canned scanner results: it executes the exact original, SHA-256-verified `scan_files_with_gitleaks` and `run_cmd` / `parse_json_maybe` functions after restricted AST extraction. The historical sources are **not imported, edited or run as modules**.

- Original scanner SHA-256: `a63a4fb8910dbec9b26733da1d87ee416587733bc897b9b753c4cd30096c1807`
- Original shell SHA-256: `f2daefdd7e39a0c1b4b45bafbf1821cb9968d4f3f7a83bb9bdb7adee3e5eb0e3`

`tests/support/archived_gitleaks_process.py` creates a local disposable executable named `gitleaks` **which is not the Gitleaks scanner**. It has no network code and supplies only predetermined synthetic JSON records. The test harness prepends its temporary directory to `PATH` and verifies that the expected stub wins executable resolution. Only files under the literal `fixture/` namespace with explicit synthetic markers can reach the archive's patch materialization routine. No user repository, GitHub clone, Wits path or historical database can enter this interface.

The original Gitleaks function writes PR-added lines to a temporary directory using their relative paths, invokes `gitleaks detect --no-git --source ... --report-format json --report-path ... --redact` through the original `subprocess.Popen` helper, parses the report and applies its baseline/placeholder filters. The tests assert report-to-finding metadata, masked evidence, missing executable/report semantics and errors. A synthetic return code 1 **with an existing report** maps to `status=ok` in the archived function; this is observed source behavior, not evidence of an installed or successful real scanner.

This is **an actual local subprocess execution with a fake deterministic scanner CLI**, not execution of real Gitleaks. It proves process and serialization wiring, but not Gitleaks detection or recall. Actual scanner binary acquisition, immutable tool version/digest, a network-disabled containerized environment, and rerunning pinned historic inputs remain open release gates.

Run `python -m unittest tests.test_miner_archived_gitleaks_process -v`, or the complete suite.
