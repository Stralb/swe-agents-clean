# Historical worker job queue / case-status contracts — disposable-only replay

## Source identity

`src/pipeline/case_builder.py` and `src/pipeline/case_status.py` were promoted **byte-for-byte** from all three miner snapshots. Their SHA-256 digests are `3c2c4e466849ac444d6a5e285c9103ece94bb91cbd5cdf072ef4e64cffa94e38` and `d011c788a5fefc08e5fb56fb8b4baf4a8aae3c4e12ec7a483f1940fb59e46e29`, respectively. Both import only already-consolidated Python miner modules.

The original `src/workers/job_queue.py` remains in historical storage and is **not directly imported** because its module imports scanner execution and the historical settings loader. Its archived SHA-256 `07a8fa5844c137816078348dbff856fdf0a41b0e53a67013a5deb441e265a73d` agrees across the three miner snapshots.

## Exact queue functions tested

`tests/support/archived_job_queue_contract.py` statically extracts and compiles ONLY the audited historical `ClaimedJob` dataclass and lifecycle methods: job seeding, priority, claiming, finish status, heartbeat, reset-on-start, and case-status synchronization. Its scope injects the exact promoted original case-builder/status functions and route reasons, with no `scan_case`, `run_scanner_job`, tool subprocess, Slurm submitter or network-enabled GitHub client.

All write operations target the existing `disposable_original_database()` fresh local temporary SQLite database. A database from another path is rejected, and source integrity is verified before compiling any archived definition. This is **not** permission to execute the original scanner or worker process against Wits.

## Behaviour pinned with synthetic fixtures

- Every unreviewed case gets five cheap jobs plus optional `codeql`, regardless of whether an individual tool later returns `not_applicable`.
- Queue seeding is idempotent; `claim_job` prioritizes pending workers and increments attempts.
- Finishing all jobs `ok` updates case status to `scanned_clean`; the original case-status layer treats an otherwise complete set containing `not_applicable` as `scan_blocked`. That original rule is recorded, not silently corrected.
- Heartbeats update a single worker record, and interrupted running jobs can be reset to pending.
- An introduced synthetic finding marks the case `needs_review`, but **no scanner ran and no security conclusion about actual cases is implied**.

## Still unimplemented

Actual `run_scanner_job` orchestration, scanner executables, CodeQL query packs, dependency tool integrations, distributed queues/spools, fault recovery under concurrency, Slurm scheduling, UI and full historical end-to-end output checks remain future engineering tasks.

Tests: `python -m unittest tests.test_miner_archived_job_queue_contract -v` and `python -m unittest discover -s tests -v`.
