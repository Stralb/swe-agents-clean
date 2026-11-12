# GitHub client consolidation: deterministic offline replay

## Engineering scope

The original GitHub client remains untouched at `historical/miner/2026-10-20-live-export/src/github/client.py` (SHA-256 `685c6e29854e92f94f1e440e0f6ee8025fb4e8133dc275bde02d99ec286be852`). Its constructor sets up `requests.Session`, creates the cache directory and may initialize a SQLite rate-limit manager. Its live methods can write cache/cooldown state, perform HTTP requests and sleep. Do not import it into test-only code or point it at historical Wits files.

## New isolated adapter

`src/github/replay_client.py` adds `ReplayGitHubClient` and a fail-closed, in-memory `FixtureTransport`. This is **new engineering code**, not a byte-preserved original module and not a production network client.

The adapter exposes the recovered client's collection-facing read methods: `get`, `paginate`, `search_repos`, `search_issues`, `search_issues_page`, `closed_pulls`, `graphql`, and `rate_limit`. It consumes exactly identified GET/POST fixtures. Unregistered requests raise `MissingFixtureError` instead of making a network call.

Mirrored contracts include resumed page numbering (`max_pages` is a number of pages), the 1,000-result GitHub Search window cap, repository search sort, issue search sort, closed PR request qualifiers, GraphQL error handling, and `GitHubAPIError` fields. Unlike the historical client, an unexpected response without an item list fails closed.

## Explicitly not implemented

- Live HTTP/GraphQL requests or authenticated GitHub sessions.
- Disk caches, token rotation, request retry/backoff, rate-limit cooldown persistence, SQLite writes or worker orchestration.
- A validated historical data replay or end-to-end collection equivalence.
- Empirical evidence about case counts, CodeQL results, or research hypotheses.

These require separately isolated, dependency-injected production components and integration tests. The adapter is suitable for synthetic unit/integration fixtures and will support testing the full collector without credentials.

## Verification

17 synthetic regression tests in `tests/test_miner_github_replay.py` pass in Python 3.11 locally. Tests cover missing fixtures, immutability, domain restrictions, page restart and limits, search-1000 boundary, propagation of unrelated 422 errors, metadata preservation, GraphQL response errors and no filesystem/network calls.

Commands:

```bash
python -m unittest tests.test_miner_github_replay -v
python -m unittest discover -s tests -v
```

Historical code and all Wits cluster files remain unchanged.
