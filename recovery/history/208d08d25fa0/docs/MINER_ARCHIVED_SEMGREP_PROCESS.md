# Archived Semgrep: local Git + deterministic synthetic rule

## Source identity

Historical Semgrep module: `historical/miner/2026-10-20-live-export/src/scanners/semgrep_scanner.py`, SHA-256 `cd5e3774840c22f3968601f005fa8e65d808b597d6d8580cc045ef0fc2feec0a`. The helper `tests/support/archived_semgrep_process.py` verifies it and compiles only an audited set of original pure/scan AST definitions, not the side-effectful archived module. Original `run_cmd`, `parse_json_maybe` and CodeQL added-line functions are SHA-verified and reused.

## Synthetic test boundary

The adapter creates an entirely local Git repository with a single, immutable synthetic commit containing `src/app.py` and `tests/test_fixture.py`. It permits only a fixed `https://example.invalid/fixture/local-semgrep` identity. **Only the original `git clone` command is redirected** to a local `file://` clone of the generated repository. The original clone/fetch/checkout and Semgrep subprocess calls are routed through exact original shell code, with strict allowed arguments and a fixed local YAML rule. No real GitHub or historical target is cloned.

For normal unit tests, a small generated executable named `semgrep` writes predetermined harmless Semgrep-shaped JSON; it is not the real scanner.

## Observed contracts

- The original scanner discovers two changed Python source files in a fabricated PR, checks out the generated head SHA, parses JSON, maps source locations to PR added lines, and stores classified findings.
- A synthetic hit under `src/app.py` is promoted as `vulnerability` and `introduced=1`; the identical hit under `tests/test_fixture.py` is retained as `semgrep_filtered` with `introduced=0`. These are **synthetic labels**, not empirical vulnerability findings.
- The exact original worker and scanner orchestration can persist the results to a brand-new disposable SQLite database, mark the scanner job `ok`, and set case status `needs_review`.
- Unapproved URLs, patch contents and source digests fail before invoking a scanner or mutating original research state.

## Limitations

Normal-suite coverage uses a fake Semgrep command, not the actual Semgrep engine. A separately labeled opt-in real-binary workflow is required to validate CLI parsing. This milestone does not prove historical Semgrep tool/rule version parity, OS-level network isolation, real scan quality, frozen corpus replication, or research conclusions.
