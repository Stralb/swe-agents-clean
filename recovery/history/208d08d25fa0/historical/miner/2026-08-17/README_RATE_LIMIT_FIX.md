# Rate-limit Hotfix: repo-window discovery + paced search

This build changes collection defaults to avoid GitHub secondary rate limits while keeping the downstream-first methodology.

## Main changes

- Default retrieval mode is now `repo_window_pr_search`, not `repo_month_pr_search`.
- The collector performs one structural PR search per repo over the full lookback window first.
- Only saturated/busy repos are adaptively split into month queries.
- Uncached GitHub search requests are paced with:
  - `GITHUB_SEARCH_MIN_INTERVAL_SECONDS` default `2.35`
  - `GITHUB_REQUEST_JITTER_SECONDS` default `0.65`
- Secondary limit handling no longer sleeps for 120 seconds inside the repo structural collector. It stops the pass cleanly so a later run can continue from cache/state.
- `CODEQL_WORKERS ?= 1` is now the Makefile default.
- UI stage filter defaults to `All`.

## Recommended collection command

```bash
make reset-db
make collect RETRIEVAL_MODE=repo_window_pr_search MAX_REPOS=50 LOOKBACK_MONTHS=12 MAX_CASES=500 MAX_CASES_PER_REPO=10 RANDOM_SEED=42
```

For testing:

```bash
make collect RETRIEVAL_MODE=repo_window_pr_search MAX_REPOS=10 LOOKBACK_MONTHS=6 MAX_CASES=100 MAX_CASES_PER_REPO=5 RANDOM_SEED=42
```

## When to use repo-month mode

Only use `RETRIEVAL_MODE=repo_month_pr_search` for final exhaustive expansion or debugging a specific time slice. It costs up to `repos × months` search calls and is much more likely to hit search/secondary limits.

## Tests

```text
89 passed, 1 skipped
```
