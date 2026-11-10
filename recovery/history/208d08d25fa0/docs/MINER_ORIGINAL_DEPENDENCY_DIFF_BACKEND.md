# Exact historical dependency-diff backend — source-equivalent promotion

## Identity and why this is active source

The recovered dependency-diff implementation is byte-identical in the three `historical/miner` snapshots (`2026-08-17`, `2026-08-19`, `2026-10-20-live-export`) and has SHA-256 `14fef8ed753361b09fbe39f09849d45cdb73264aad93f542d6d8e2d7e95e43d7` (Git blob `1ee3bc602a9c2363dfb133895940c70c40ef934d`). It has only pure parsing and version-comparison functions: no file writes, cloning, scanner executable, network or worker side effects. Therefore the exact same original blob is promoted, without edits, to `src/scanners/dependency_diff.py`.

`pyproject.toml` adds `src.scanners` to its package set and pins `packaging==25.0`. CI installs exactly its universal wheel by official PyPI SHA-256 `29572ef2b1f17581046b3a2227d5c611fb25ec70ca1ba8554b24b0e69331a484` via `--require-hashes --no-deps --only-binary=:all:` before executing tests. This is an **explicit current candidate dependency**, not evidence that the August/October historical scanner used packaging 25.0. Python 3.11 and that dependency are separately asserted in the contract tests. The dependency has no declared transitive dependencies.

## What was tested

`tests/test_miner_original_dependency_diff.py` compares all four file byte hashes (three historical copies plus active source) and tests original output shapes directly, including:

- `requirements.txt` downgrades, constraint widening at equal versions, invalid/untagged versions with changed operators, multiple-hunk added-side line references, manifest suffix matching, unchanged/upgraded and new dependencies, JSON package changes.
- The exact original `ArchivedFixtureWorker` dispatch → original `scan_case()` → active original pure `detect_dependency_regressions()` → original SQLite scanner run and introduced `dependency` finding → original case `needs_review` status, all on a newly created disposable database with a strictly approved `fixture/requirements.txt` diff.
- Historical cache behavior and original `_clear_scanner` cross-scanner deletion on forced dependency-diff rescan; this is pinned as a failure mode rather than rewritten.
- A changed dependency file lacking patch text yields **no analyzer findings**. A syntactically ordinary `package.json` string field with a version-shaped value can be falsely interpreted as a dependency due to the historical `PKG_JSON_RE` heuristic. Path recognition uses `endswith` and can admit unexpected basenames. This is deterministic original behavior, **not a statement about how often these issues occurred historically**.

## Limitations

The original implementation is not a full package-ecosystem parser. It compares added and removed lines heuristically and does not establish that a downgrade introduced a security vulnerability. Additional source coverage, tool applicability, historical case-level reproducibility and scanner rule provenance remain release blockers. No Wits or user Git repositories are accessed.
