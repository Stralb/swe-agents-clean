# Exact archived worker dispatcher: synthetic-only integration milestone

## What is now connected

`tests/support/archived_fixture_worker.py` independently SHA-256 verifies the recovered `historical/miner/2026-10-20-live-export/src/workers/job_queue.py`, compiles only its unmodified AST definitions `_case_select`, `_scanner_config_for_job` and `run_scanner_job`, and binds the function to existing SHA-verified, disposable-only queue lifecycle methods.

`run_scanner_job` is the **exact original worker dispatcher**, not a reimplementation. Its injected `scan_case` is the already-audited exact original archived scanner orchestrator wired to six synthetic-only backend providers. The `Settings` type is replaced by an explicitly constrained `FixtureWorkerSettings`; scanner settings, repo URL, job identity, and database allocation are checked before invocation. No original worker or scanner module is imported.

## Verified contract scenarios

- Exact archived `seed_scanner_jobs` → `claim_job` → `run_scanner_job` → original scanner backend handling → original `finish_job` → case-status synchronization executes all six job types against a disposable original-schema SQLite database.
- All six jobs can complete `ok` when explicit synthetic results are supplied, including original CodeQL snapshot status aggregation. A simulated scanner error remains an error.
- A missing synthetic provider uses the test-only `MissingScannerFixture(BaseException)` guard, which is not masked by the historical worker's `except Exception` block. **The job is left running**; the original reset/reclaim mechanism increments attempts and permits a re-run with a complete fixture. This is not an assertion that the real worker should use BaseException; it prevents a false success in the laboratory harness.
- The original SQLite `claim_job` critical section is exercised with six concurrent fixture callers; every returned job ID must be unique.
- Invalid settings, unclaimed jobs, and non-`example.invalid` repository URLs are rejected before backend invocation.

## Limitations and next gates

This is **worker dispatch integration**, not a real scanner run or distributed Slurm demonstration. Assertions use only synthetic fixtures, no scanner executables, no network and no Wits data. The historical scanner and worker source hashes are not changed. The next gates are (1) an explicit opt-in scanner executable environment with pinned binaries and a harmless local repository fixture, (2) tool-version and stdout/SARIF provenance, (3) robust worker recovery and concurrency under sustained load, and (4) frozen input/output parity.

Run `python -m unittest tests.test_miner_archived_fixture_worker -v` or `python -m unittest discover -s tests -v`. Maintain this as a test-only utility. Never expose these helpers as production commands against a non-disposable database.
