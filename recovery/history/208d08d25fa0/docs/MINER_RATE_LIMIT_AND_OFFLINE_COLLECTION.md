# Read-only rate-limit policy and synthetic collection smoke tests

## Recovery boundary

The original `historical/miner/2026-10-20-live-export/src/github/rate_limit.py` remains unchanged. The old `RateLimitManager` uses SQLite for header state, calls `db.execute`, and can block/sleep. Do **not** initialize it against the Wits database or scheduler.

`src/github/rate_limit_policy.py` extracts the arithmetic as deterministic functions. It accepts explicit response headers and a caller-supplied current timestamp, and returns how many seconds the original manager would wait. It never opens a DB, persists state, or sleeps. Preserve original choices: separate search and core reserves, an inclusive reserve threshold, a two-second reset margin, and a one-second minimum delay for an exhausted bucket.

The adapter is **new engineering code**, not a byte-preserved historical module. Its outputs have been verified against synthetic edge cases; they are not frozen historical rate-limit traces.

## Integration smoke tests

`tests/test_miner_offline_collection_smoke.py` wires the new fixture-backed ReplayGitHubClient into **byte-preserved original modules**: `agentic_discovery`, `ai_markers`, `issue_linker`, `issue_filters`, `bot_filter` and `pr_filters`. A synthetic PR, linked issue and file list traverse the interfaces without HTTP, credentials, files or SQLite.

This validates a small cross-module contract. It is not the 3,000-line historical collector, does not save cases, and makes no claims about the 3,809-workflow cohort.

## Tests

Nine deterministic rate-limit tests and three collection-smoke tests pass locally (Python 3.11). Run all tests in a checkout with:

```bash
python -m unittest discover -s tests -v
```

## Remaining engineering integration

Next work: isolate the historical GitHubClient retry/cache/cooldown mechanisms behind injectable interfaces; extract a disposable SQLite schema adapter; then exercise the actual collector using an ephemeral database, not the original Wits storage. Exact source-specific behavior must be checked against archived tests before promoting further modules.
