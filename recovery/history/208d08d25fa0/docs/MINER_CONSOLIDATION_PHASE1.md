# Miner engineering consolidation — phase 1

**Scope: source recovery and reproducible software engineering, not new research.**

Source branch: `recovery/source-snapshots-20261020-235319-2ca255c5` at commit `92a5221393c8080ce67feebafdea1f465ffd1c26`.
The active code in this phase is deliberately a narrow **read-only, zero-network foundation**. It cannot collect PRs, access databases, schedule jobs, or execute scanners.

## Static dependency and entrypoint inventory

The `tools/miner_import_inventory.py` command reads the verified source-only ZIP **without extracting, importing or executing historical code**. Its results for the live October 20 miner are committed as `provenance/miner_live_static_import_inventory.csv`.

| Historical Python source area | Files parsing successfully |
| --- | ---: |
| `src/` | 66 |
| `scripts/` | 20 |
| `ui/` | 22 |
| `analysis/` | 16 |
| `tests/` | 47 |
| **Total** | **171/171** |

The inventory finds **18 distinct direct third-party import names** across these 171 files. Base `requirements.txt` contains version **lower bounds**, not a pinned lock; it does not fully enumerate the packages imported by the standalone analyses (e.g., NumPy, SciPy, scikit-learn, HDBSCAN, ruptures). Some research scripts also use sibling bare imports, classified as local rather than incorrectly treated as third-party packages.

Static heuristic flags occur in 53 files with top-level calls and 89 files with possibly mutating method/API references. **These are conservative search leads, not counts of dangerous files.** Top-level calls such as `re.compile` are usually harmless; a method named `execute` could be DB-mutating or not. We have not executed these 171 historical modules.

Run this verification on a local copy of the staging ZIP:

```bash
python tools/miner_import_inventory.py /path/to/arno_code_history_source_only_20261020_v2.zip
python tools/miner_import_inventory.py /path/to/arno_code_history_source_only_20261020_v2.zip --format csv
```

Both commands print to stdout and create no output files. The produced CSV is a reproducible *snapshot inventory*, not a dependency lock or validated architecture graph.

## First promoted source modules

Four modules are **byte-for-byte identical** across August 17, August 19 and October 20; see `provenance/miner_phase1_promoted_sources.csv` for exact SHA-256s and paths.

| Active path | Engineering responsibility | Direct imports |
| --- | --- | --- |
| `src/markers/ai_markers.py` | Classify high-/medium-confidence markers by candidate text | Standard library |
| `src/markers/upstream_features.py` | Extract non-filtering issue text features | Standard library |
| `src/github/issue_linker.py` | Extract current-repository issue references from PR text | Standard library |
| `src/filters/pr_filters.py` | Categorize PR files, preserve ambiguous changed-file sets | Standard library |

The original source bytes were copied without edits. Existing pytest-style historical fixtures were translated into new standard-library `unittest` smoke/regression tests; additional synthetic corner cases were added separately. CI also confirms each promoted source file still equals the three archived copies from the same Git tree.

These tests verify **representative behavior and source identity**, not comprehensive integration with all real GitHub metadata. They do not change inclusion criteria or produce new scientific outcomes.

## Explicitly deferred

- **Collection and GitHub access:** `src/github/client.py`, `src/github/rate_limit.py`, `src/pipeline/collect_pipeline.py`. Audit pagination, API rates, credentials and historical collection SQL under mocks before promotion.
- **Database and concurrency:** `src/db/database.py`, `src/distributed/local_coordinator.py` and worker/queue code. Source has runtime database writes, hard-coded cluster paths, coordinator state and an unresolved change in the database writer target. Never test against the original Wits database.
- **Scanner execution:** `src/scanners/` plus CodeQL and other binaries; requires exact executable versions, query configuration and a disposable filesystem/database, not the historical scan outputs.
- **Web review UI:** August 19 introduced five UI modules absent from live. Review as a separate variant with pinned application dependencies and mocked data adapters.
- **Standalone experiments:** Discovery, C/D coding, matched controls, T1/T2 and October O/W/P remain immutable, independently versioned historical code. They are not combined with the miner simply because their filenames are newer.

## CI validation and safety

```bash
python -m compileall -q tools analysis src tests
python -m unittest discover -s tests -v
```

These commands run the standalone verification tools and the newly promoted pure modules only. They **do not** execute any entrypoint under `historical/` or invoke Wits/CodeQL/GitHub APIs. Testing on a new branch built from the recovery branch preserves the exact historical snapshots; merging into `main` remains a separate reviewed decision.

### Promotion gates for the next phase

1. Inventory original settings/configuration/data schema without running its loaders.
2. Unit-test configuration and issue/PR collector semantics against synthetic responses.
3. Isolate DB schema/migrations to a newly created **local** fixture and prove no historical path can be written.
4. Recover test/runtime dependency lock and exact external binary contracts.
5. Attach original source-path and SHA provenance to every subsequent promoted module.

**No Wits cluster files, jobs, or original research results were modified.**
