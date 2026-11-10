# Recovered base SQLite schema — memory-only integration

## Source and scope

The exact 11,380-byte `src/db/schema.sql` was reused as the **same Git blob** from the three archived miner snapshots. Its SHA-256 is `1bd6e73515570b6e1248e8ecb9ded6cd3079b24e73d964de60b52a1a01aa4853`. The original historical scripts and Wits databases were not changed.

The source defines 24 application tables and 13 explicit named indexes in SQLite, including repositories, issues, PRs, issue/PR links, cases, scanner runs/findings/jobs, GitHub rate limits, and daemon controls. These counts exclude SQLite internal auto-indexes.

## Safe test adapter

`src/db/ephemeral.py` validates the bundled schema SHA-256 and invokes SQLite **only** with `:memory:`. There is no database path argument, no file-backed fallback, no historical import, no Wits connection and no worker/job execution. After applying the schema it asserts that the SQLite database list contains only an in-memory main database and that foreign keys are enabled.

Eight new synthetic unit tests confirm exact archival source bytes, schema shape, memory-only connection, foreign-key constraints, unique repository names and an example repo → issue → PR → case join. A deliberately corrupted schema is rejected **before** SQLite initialization.

## Not yet recovered as active code

The archived `src/db/database.py` implements additional runtime schema migrations and path-based connections, WAL/locking policy, read-only UI modes and many application-specific SQL methods. **None of those have been promoted or executed**. The in-memory schema covers the frozen base DDL only, not the full miner database or its production runtime.

The original historical SQLite databases and their data remain untouched and outside the new GitHub source package.

## Local verification

```bash
python -m unittest tests.test_miner_ephemeral_schema -v
python -m unittest discover -s tests -v
```
