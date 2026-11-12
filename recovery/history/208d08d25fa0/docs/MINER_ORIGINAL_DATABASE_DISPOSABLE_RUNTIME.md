# Original miner Database runtime: disposable-file verification

**Scope:** engineering reconstruction using byte-preserved source. Not a new research experiment or a verified production miner. No Wits, research database, Slurm service, scanner or third-party repository was contacted or modified.

## Provenance

- `src/db/database.py` is exactly the original `src/db/database.py` in the August 17, August 19 and October 20 snapshots, SHA-256 `3412fedd504f1b78875fc2303a4e193a82d05bcfe567c3ecedea7cc697f77b90` (23,526 bytes).
- The original module source remains untouched under all three `historical/miner/` prefixes.
- `src/db/schema.sql` is separately byte-preserved and checksum-verified; see `docs/MINER_EPHEMERAL_SQLITE_SCHEMA.md`.

## New safe entrypoint

`src/db/disposable_harness.py` provides `disposable_original_database()`. The factory accepts **no path**, creates a new local `TemporaryDirectory`, constructs the unchanged `Database` within that directory, initializes the recorded schema, and cleans up the local files when the context exits (including exception paths). It does not use the Wits cluster or existing data.

Example for **local disposable tests only**:

```python
from src.db.disposable_harness import disposable_original_database

with disposable_original_database() as db:
    print(db.one("SELECT COUNT(*) AS n FROM repos"))
```

## Verified legacy behaviours

Synthetic tests cover schema initialization, default tag seeding, repeated schema setup, SQLite foreign keys, repository INSERT OR IGNORE, issue and PR upsert, issue-PR links, case upsert, PR-file replacement, read-only query mode, and failure to write without a command spool.

The original `apply_migrations()` also has important **mutating** behavior:

1. Backfills five scanner jobs per unreviewed/unexcluded case, and can set such cases to `scanner_running`.
2. Rewrites `skipped` scanner runs/jobs to `not_applicable` and **deletes** legacy `scanner_jobs` rows with job types `source_code` and `dependency`.
3. Rewrites/reset some old `retrieval_queries` rows, including counters, pagination state and status, to enable replay.
4. Adds columns/tables/indexes for later miner versions.

These are genuine **source-code operations**, not claims that the Wits data currently needs correction. The tests intentionally demonstrate them on newly created **temporary local records**. The original module is therefore **unsafe to point at historical databases before a separate clone-and-validate procedure**. No such operation was performed against real data.

## Changes and limitations

- Original `Database` class: exact Git blob reused, **no fixes**.
- New `disposable_original_database()` factory: separately authored engineering code with no caller-controlled path.
- The class itself still accepts arbitrary file paths and performs writes/migrations. Importing the module defines the class but does not initialize a database. The factory is the only supported entrypoint for these tests.
- The historical read-only mode uses SQLite `mode=ro&immutable=1`, which should not be treated as a general live-WAL snapshot guarantee.
- The original delayed write/spool path is not exercised: `src.distributed.spool` remains historical and is not integrated.
- Scanner queue execution, UI mutations, database provenance and end-to-end frozen dataset reproduction are still outstanding.

## Local tests

`tests/test_miner_original_disposable_database.py` and `tests/test_miner_disposable_database_harness.py` add **15** tests. The broader offline codebase passes **142/142 tests** in the local Python environment (127 pre-existing + 15 new).

```bash
python -m unittest discover -s tests -v
```

No source archive files were altered. The draft PR should remain unmerged until the remaining system integration tests pass.
