# Verified real-Gitleaks candidate toolchain: synthetic-only CI gate

## Scope

The independent workflow `.github/workflows/synthetic-gitleaks.yml` downloads **Gitleaks 8.30.1 for Linux x64** from its official GitHub release `v8.30.1`, verifies archive SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`, and installs it to `RUNNER_TEMP` on an ephemeral GitHub-hosted runner. Asset name, version and digest were independently retrieved from the official [GitHub release metadata](https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1) on 21 October 2026.

The opt-in test `tests/test_miner_archived_real_gitleaks_smoke.py` runs the **exact original archived** SHA-verified `scan_files_with_gitleaks()` and original `run_cmd()` functions with one harmless fabricated `fixture/app.ts` diff. A temporary TOML configuration provides a single synthetic-only detection rule, so passing the test proves real executable invocation and original JSON parsing, **not correctness of the historically deployed rule pack**. The fabricated token does not correspond to an active credential.

The test is skipped in ordinary `verify.yml` CI; the dedicated workflow is limited to pushes to `work/miner-core-consolidation-20261021`. This is an independently labeled smoke gate, not a replacement for offline unit tests or the historical output-parity gate.

## Security and reproducibility boundaries

- No Wits cluster account, historical DB, historical target GitHub repositories, or public miner research repositories are touched.
- The repository is checked out for test code only; the real scanner receives exclusively a temporary materialized synthetic patch and a temporary synthetic rule configuration.
- The archive checksum protects acquisition against an unexpected binary, and the version is checked at runtime. No unverified install script or `latest` tag is used.
- The GitHub-hosted runner itself still has outbound network during artifact download and running the test. This stage **does not prove an OS-level network-disabled sandbox**, despite the isolated files. Network-namespace confinement or a pinned container image must be established before using untrusted target repositories.
- Even if the workflow passes, the release is a **candidate executable**, not evidence that `v8.30.1` was the version used to generate the historical findings; version provenance and frozen result parity remain unresolved.

To review the result, inspect the named Actions workflow for the exact commit. Do not run a real scanner on user/prod repositories using this harness.


## Original worker-to-real-Gitleaks handoff

A second opt-in smoke test follows the original `seed_scanner_jobs` → `claim_job` → exact archived `run_scanner_job` → original `scan_case` → actual Gitleaks 8.30.1 executable → original `scanner_runs`/`scanner_findings` SQLite writes → exact archived `finish_job` → `needs_review` case-status chain. The database is `disposable_original_database()`; its only PR is a fabricated `fixture/app.ts` containing a predetermined dummy marker. The injector allows no other file and no non-synthetic repository. It asserts the scanner finding is redacted and that the original worker marks the job successful.

This integrates **one actual scanner binary** into the reconstructed worker pipeline. Other scanner binaries, original historical rule sets and full-corpus reproducibility remain untested. The CI host remains network-capable and must not be treated as a hardened hostile-repository sandbox.
