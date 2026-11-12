# Candidate Semgrep engine: checksum-verified synthetic-only CI

## Installation provenance

A dedicated, branch-restricted GitHub Actions job downloads the official Semgrep **1.181.0** wheel for CPython 3.11 / Linux x86-64, verifies its PyPI SHA-256 `c142ec04a2ed144970cb0a92f6877651dd3c088505eec737bb7f4db7ae5f0ffa`, and installs it in a temporary Python virtual environment. The wheel was published on **14 October 2026** and its SHA-256 is listed at https://pypi.org/project/semgrep/1.181.0/. This is a candidate modern executable, **not the proven version of the historical Semgrep runs**.

The workflow records the CLI version and dependency versions (`pip freeze`) in the Actions log. The **top-level wheel is hash-pinned**, but its Python **transitive dependencies are not yet lockfile-hash-pinned**. This remains a reproducibility gap.

## Original-source integration

`tests/test_miner_archived_real_semgrep_smoke.py` invokes the exact SHA-verified original `scan_head_with_semgrep` and original shell helper on a locally generated Git repository whose only files contain a harmless fabricated function call. The original remote Git clone command is substituted with a local `file://` clone of the test-only fixture, and only explicitly approved Git and Semgrep commands are permitted. The original Semgrep arguments are preserved; the rule is a fixed local YAML file rather than a remotely resolved `p/security-audit` suite.

The two smoke scenarios verify (1) parser/added-line association and promoted versus test-path-filtered source findings, and (2) exact original worker dispatch into the original disposable SQLite scanner tables and case-status code. Only the known fabricated code and synthetic issue/PR rows are used.

## Boundaries

No third-party repository or original research database is scanned. The CI machine is network-capable for wheel/dependency acquisition; this is **not an OS-level no-network sandbox**. The workflow does not prove the historical Semgrep configuration or tool version, Semgrep's performance on real vulnerabilities, or regeneration of any frozen published result. Missing real OSV, Trivy and CodeQL integrations remain separate work.


## Hardened candidate CI path

The independent `archived-semgrep-network-none` job in `.github/workflows/synthetic-semgrep.yml` verifies the same top-level wheel checksum, builds a throwaway image from `tests/support/Dockerfile.semgrep-synthetic`, and launches the same two real-engine tests with Docker `--network none`, read-only root filesystem and repository mount, `--cap-drop ALL`, `no-new-privileges`, non-root UID/GID, pids and memory limits, and a disposable `/tmp` tmpfs. The image build can access the network to acquire dependencies, **but the smoke-test container cannot route outgoing traffic**.

This provides OS-level network namespace isolation for the fabricated test cases, in addition to the code-level restrictions. It is **not yet** a fully authenticated or signed reproducible container: the upstream Python base-image tag and Semgrep's transitive Python dependencies remain unfrozen. Further defense-in-depth (hash-pinned dependency lockfiles, image digest, resource quotas and restricted mounts for real repositories) is required before using potentially malicious issue/PR content.
