# Genuine Trivy candidate against immutable public advisory data

The dedicated CI job `.github/workflows/synthetic-trivy-frozen-db.yml` downloads the genuine Trivy **v0.76.1** Linux 64-bit tarball with SHA-256 `c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0` from the official release.

Instead of a floating vulnerability DB tag, it downloads a specifically identified public Trivy-DB OCI manifest:

- Publisher: [aquasecurity/trivy-db](https://github.com/aquasecurity/trivy-db/pkgs/container/trivy-db/1292506144)
- OCI manifest SHA-256: `bfeab4910aea63f6053c238c6caa085583fdaea9f630150d3265a1e38c2544db`
- OCI vulnerability database layer SHA-256: `f834840e1109c7a3dc46244cf80bd00485a77a6a8ffe825fcd2aedbf22e5ec0d`
- Advisory snapshot built approximately **25 September 2026**, **not** the historical study scanner DB and **not** a dynamically refreshed latest database.

The CI job verifies both hashes before extraction, prints SHA-256 of the extracted database components and mounts the database read-only at `/tmp/trivy-cache/db` into a container with `--network none`, read-only source/root FS, non-root execution, dropped capabilities and strict resource limits.

The tests call the exact SHA-verified historical `_scan_snapshot()` and `_introduced_findings()` functions with the real Trivy CLI and two locally fabricated `fixture/requirements.txt` files. The only external source data is a **frozen public vulnerability database**; the package manifests contain well-known public `requests` release versions, not confidential code or credentials. The test requires real JSON results, a blocking status on errors, and an introduced finding linked to the changed manifest target. No real GitHub repository, Wits file or historical production DB is read.

**Limitations:** The scanner binary, DB and Python base image are candidate versions, not historical provenance. The Python/OS image still requires dependency/image digest pinning. The test does not claim exact statistical replication or transfer any result to the historical positive-case set.

Use the CI result only when the job completes successfully. A failed DB download, an expired schema or a scanner rule mismatch must remain a visible failure, not be coerced into a clean result.


## Full original worktree and worker integration

The original frozen-DB test also now exercises the exact archived `scan_dependency_snapshots_with_trivy` driver, not merely its `_scan_snapshot` helper. `tests/support/archived_real_trivy_snapshot.py` creates a two-commit local Git repository whose only changed file is a fabricated `fixture/requirements.txt`: base `requests==2.32.5`, head `requests==2.19.1`. Only the archived `git clone` source URL is redirected to that generated local fixture; the archived Git fetch and base/head worktree commands execute unchanged under strict argument and path allowlists.

The genuine Trivy candidate scans both worktrees against the *same* immutable read-only September 2026 database and emits vulnerability results. The historical Trivy attribution functions select newly introduced findings touching the changed dependency target. A second test follows that evidence through the exact archived job-queue worker, scanner recorder, SQLite finding writes and case-status update. Both tests fail if a non-synthetic repository, a different commit SHA or a missing database is supplied.

The candidate public advisory database does not establish which advisory snapshot the original research used. The test is a controlled offline replication of the **software pathway**, not reproduction of the published empirical sample.


## Verified immutable OCI component digests

On the [successful three-test real-Trivy run](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39623833418), the independently verified and extracted components were:

| Component | SHA-256 |
| --- | --- |
| OCI manifest | `bfeab4910aea63f6053c238c6caa085583fdaea9f630150d3265a1e38c2544db` |
| OCI compressed DB layer | `f834840e1109c7a3dc46244cf80bd00485a77a6a8ffe825fcd2aedbf22e5ec0d` |
| `metadata.json` | `12549ff5c25f822dafc1cbc683bd9eb37c521db79a751275b938b35f3920644a` |
| `trivy.db` (1,439,383,552 bytes) | `fab60ddec009c8106a9d13d6e725b716fd0930c8f03351e545ac48d75f0c1bc2` |

The complete archived top-level Git base/head and worker→SQLite paths then passed using the same fixed offline database. This DB was updated 25 September and expired for live currency on 26 September 2026; it must not be represented as an up-to-date security scanner dataset or the original research DB.
