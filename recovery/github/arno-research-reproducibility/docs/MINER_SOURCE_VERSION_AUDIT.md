# Miner Source Version Audit — August Snapshots vs Wits Export

**Date:** 20 October 2026. **Method:** content SHA-256 comparison of matching paths under `src/`, `scripts/`, `tests/`, `ui/`, and `analysis/` in three exact registered archives. Excludes cache files, `.before-*` backups, `backups/`, and runtime/database files from the *active source* comparison. Original archives remain immutable and separately registered.

## Compared candidates

- `SRC_AUG17`: `malicious-issue-miner-rate-smart-main(1).zip` — 152 selected code-path files.
- `SRC_AUG19`: `malicious-issue-miner-upstream-downstream-review-ui(1).zip` — 157 selected code-path files.
- `SRC_LIVE`: `miner_live_source_readonly.tar.gz` — 184 selected code-path files.

The union has **189 distinct source paths**. See `provenance/miner_source_comparison.csv` for every file SHA and classification.

| Classification | Paths |
| --- | ---: |
| Identical in all three | 150 |
| Changed in live relative to August 17 | 1 |
| August 19 UI variant while live retains August 17 version | 1 |
| August 19 only (missing from live) | 5 |
| Live only (not in either August snapshot) | 32 |
| **Total** | **189** |

## Concrete differences

### Live coordinator modification (not yet promoted)

`src/distributed/local_coordinator.py` differs from the August snapshots. The visible change in its database-selection logic replaces a separately named coordinator working database with the shared continuation database directly (`local_database = shared_database`), with additional status logging. The comment asserts a single writer. This is a **stateful execution-path change**, not merely formatting. We have **not** run it, proven that the single-writer assumption holds, or established that it reproduces frozen historical results. **Do not execute against original frozen databases.**

### Review UI branch divergence

`ui/app.py` in the August 19 archive adds a selectable Parquet backend and uses additional research-review modules. Those five additional source paths exist in August 19 but not live:

- `ui/parquet_store.py`
- `ui/research_layer.py`
- `ui/review_store.py`
- `ui/views/parquet_app.py`
- `ui/views/research_review.py`

This is a separate candidate UI branch, not evidence of an improved or active miner pipeline. Its dependencies, data contract and tests must be inspected before promoting it.

### Scanner baseline is unchanged across the three snapshots

All eight Python paths under `src/scanners/` (including `__init__.py`) have identical source bytes across these archives. So do `src/github/issue_linker.py` and `src/pipeline/scan_pipeline.py`. **This only compares source versions**. It does not verify historical scanner binaries, query packs, CLI flags, asynchronous job state, scanner revalidations, dependencies, or the October CodeQL experiments, which used additional scripts and evidence outside these snapshots.

### Research code is spread across directories

The 32 source-path additions found only in the live export include the full-corpus v1.1/v2 discovery scripts, scanner revalidation scripts and other historical analysis material. Numerous other research programs (C/D, provenance closure, matched controls, T1/T2, v2.1/v2.2 discovery and October O/W/P) were supplied as **separate** archives or live under `research_artifacts`. They must remain independent sources until their version and provenance are validated.

## Baseline decision

- **No complete miner candidate is approved as the new canonical implementation yet.**
- Preserve all three source candidates and their hashes as historical inputs.
- Start from atomic, independently validated functions, not a wholesale checkout of either the live source or the August 19 UI branch.
- Import original code only after security/licence review and tests tied to the actual research claim.
- The cluster's three recorded Git commits (August 1, 5, 17) do **not** account for the many local backup snapshots and separately archived experiments.

## Recreate this audit offline

```bash
python tools/compare_source_snapshots.py \
  '/path/to/malicious-issue-miner-rate-smart-main(1).zip' \
  '/path/to/malicious-issue-miner-upstream-downstream-review-ui(1).zip' \
  '/path/to/miner_live_source_readonly.tar.gz' \
  --csv '/path/to/NEW_NONEXISTING_output.csv'
```

The `--csv` option refuses to overwrite an existing file.
