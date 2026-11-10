# Integrated historical collect() → targeted handler replay (offline)

## Goal and exact historical sources

The old miner's `collect()` dispatcher was previously tested with inert collector-handler spies, while `_collect_targeted_stream_search()` and `_process_pr()` were tested separately. This stage **joins the actual archived implementations** using the existing SHA-256-checked allowlist extraction. No historical code is edited or promoted as an executable entrypoint.

Input: `historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py`, SHA-256 `5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750`, identical to both August miner snapshots.

`tests/support/connected_original_dispatch.py` binds the original `collect()` to the original `_collect_targeted_stream_search`, which itself binds the original `_process_pr`. It supplies a `FixtureSearchOnly` client containing explicit in-memory responses and a `Database` created by the disposable SQLite harness.

## Safety controls

- `Database(settings.db_path)` accepts only the **literal** non-path sentinel `fixture:database`; its injected factory returns an independently validated, already-created disposable original database.
- `GitHubClient(settings.github_token)` accepts only `NON_SECRET_FIXTURE_TOKEN` and returns an explicitly supplied `FixtureSearchOnly` replay object. The original network-enabled `GitHubClient` is never imported.
- `collect()` reads only a supplied config dictionary and a stub environment. Wall-clock use and sleeps are handled by the existing targeted replay clock; network response gaps fail closed.
- Every other historical retrieval mode is **explicitly unsupported** and fails before entering real collector code. A stub must never make an unsupported mode appear to have completed.
- All original database writes happen only within a newly allocated temporary database; the Wits cluster and frozen research artifacts are out of scope.

## Integration contract

Tests cover `collect()` dispatch to targeted handlers, real original query creation, persisted retrieval cursor, case and retrieval creation, issue/PR relationships and original marker/feature data, re-running exhausted queries without re-fetching, 500 retryable search state, deliberate failure on missing fixtures, rejection of live DB paths and credentials, and closed routing of unavailable modes.

**Limits:** This is a synthetic end-to-end targeted *metadata collection* path, not full historical reproduction. It omits other real original retrieval handlers, HTTP/token/cache/rate-limit transport, distributed worker orchestration, actual scanner execution, Streamlit UI, original environment lock and comparison against frozen results. These must not be reported as completed.

## Tests

`python -m unittest tests.test_miner_connected_original_dispatch -v`

`python -m unittest discover -s tests -v`
