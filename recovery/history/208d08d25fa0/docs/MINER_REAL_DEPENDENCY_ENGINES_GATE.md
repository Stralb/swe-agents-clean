# Genuine OSV/Trivy candidate binaries — offline-only reproducibility gate

The independent workflow `.github/workflows/synthetic-dependency-engines.yml` acquires official OSV-Scanner **v2.6.0** (Linux amd64 **binary SHA-256** `ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108`) and Trivy **v0.76.1** (Linux 64-bit **tarball SHA-256** `c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0`). Both digests come from the publishers' official GitHub releases. These candidate versions are **not claimed to be the historical 2026 scanner versions**.

### Genuine offline OSV semantics

The exact archived `_scan_dir()` function, compiled from hash-verified historical source, is supplied a single `fixture/requirements.txt` containing a fabricated package. The test builds its own synthetic OSV offline database ZIP with one known-fake advisory and runs the **real OSV engine** against it. Its allowlisted subprocess adapter adds `--offline-vulnerabilities` and `--local-db-path` (and `--no-resolve`) **only for the synthetic test**. This is a clearly labeled *safety adapter deviation* from the original command, not an assertion of byte-identical runtime arguments. Assertions require exactly one attributable synthetic advisory, or CI must fail rather than mark the case as clean.

### Genuine offline Trivy semantics

The exact archived `_scan_snapshot()` function is supplied a fabricated requirements file and the real Trivy binary, **without any real Trivy vulnerability DB**. The test is designed to prove the binary's CLI runs and that absence of the advisory DB is a blocking error, **not a negative finding**. There is intentionally no assumption that an empty engine result means the project is safe. Creating a checksum-pinned Trivy DB snapshot with fixed contents remains an explicit next gate.

### Environment and research boundaries

The host downloads published binaries over the network and checksum-verifies them; **only the scan-time container** uses Docker `--network none`, non-root UID, read-only repository/root filesystem, a disposable temporary filesystem, dropped capabilities, no-new-privileges, and CPU/memory/PID limits. The base image and system packages are not yet fully digest-pinned. Only harmless generated fixture code is scanned; no private historical target is processed or Wits accessed.

These tests establish candidate executable compatibility and fail-closed behavior, not the original historical findings, historical tool versions or statistical reproduction. See `docs/MINER_SCANNER_RUNTIME_GATES_20261021.md`.


## Full original OSV snapshot → worker pipeline

In addition to the baseline original `_scan_dir` parser check, `tests/support/archived_real_osv_snapshot.py` generates a two-commit local Git repository with one fabricated Python requirement (`arno-synthetic-fixture-lib`, version `2.0.0` at base and `1.0.0` at head). Its companion test runs the exact SHA-pinned archived `scan_dependency_snapshots()`, historical `git clone` (redirected only to the local `file://` fixture), `git fetch`, `git ls-tree`, `git show`, and the original base/head scanner parser. Only the OSV CLI arguments are augmented with explicit offline/local-database options. An independent test follows the result through exact original `seed_scanner_jobs`, `claim_job`, `run_scanner_job`, `scan_case`, `scanner_runs`, `scanner_findings` and case-stage assignment using a disposable original SQLite database.

This test requires **one genuinely detected fabricated advisory at the head and none at the base**. It will fail if OSV cannot read the local fake database, if Git reconstructs the wrong snapshot, if the original attribution differs, or if worker persistence fails. It never processes a real repository or a real advisory.
