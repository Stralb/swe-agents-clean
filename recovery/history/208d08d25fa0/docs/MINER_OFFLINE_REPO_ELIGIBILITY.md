# GitHub repository eligibility — fixture-backed, in-memory reconstruction

**Software reconstruction only.** This does not mine GitHub, run research
experiments or touch the Wits cluster. Original snapshots are preserved.

## Historical source contract

`historical/miner/2026-10-20-live-export/src/pipeline/repo_eligibility.py`
SHA-256 `38f6a99822ba4cd4908cc233b36b6aa511de1b1dc5dfc65d0054242a2836014f`.

The historical `evaluate_repo_eligibility` implements a repository-level
eligibility gate based on GitHub Linguist's language-byte totals:

- Default `min_stars=100` and `min_js_ts_share=0.50`.
- Sum bytes for exact labels `JavaScript` and `TypeScript`; denominator is
  all nonnegative language bytes.
- Exclusion precedence: archived; fork; disabled issues; stars; no language
  bytes; JS/TS share; otherwise eligible.
- Reuse a cached row only when case-insensitive repository name, minimum
  stars, and `min_js_ts_share` (within `1e-7`) match.
- Exactly **one row per repository** in the original cache table; calculating
  with new threshold values replaces the previously cached threshold.
- Force refresh bypasses the cached result. Original fetched repo metadata is
  optional; when supplied and nonempty it avoids a separate repo endpoint GET.

This is different from the separately archived `_repo_passes_universe`
screen, whose default star threshold is 200.

## New code and integration

`src/pipeline/offline_repo_eligibility.py` is a separately written adapter
that uses `ReplayGitHubClient` response fixtures and SQLite's *exact base*
`repo_eligibility` table in `:memory:`. It records the original reason codes,
byte breakdown, source language dictionary and cache keys. It requires the
caller to supply explicit memory-only dependencies and has no live HTTP or
file-backed SQLite fallback.

`collect_fixture_pr(...)` can opt in via:

```python
FixtureCollectionPolicy(
    require_repo_js_ts_share=True,
    repo_eligibility_min_stars=100,
    repo_eligibility_min_js_ts_share=0.50,
    repo_eligibility_force_refresh=False,
)
```

When enabled, the repository eligibility decision is evaluated **before PR
metadata is fetched**. Its result is cached as its own transaction even if the
subsequent PR cannot be collected. A rejected repo records an explicit
`repo_eligibility:<original_reason>` in the *fixture* exclusion log; that
prefix is an adapter convention, not a claim of bit-for-bit historical logging.

The original module's `Database` wrapper requires a live file path. It was
not imported; the adapter uses the already verified exact base schema.

## Safety and deliberate differences

- The adapter accepts only `owner/repo` names. The original accepted a
  looser `str(full_name).strip()` and could construct malformed paths.
- Language response fixtures must be mappings. The original converted
  responses using `dict(languages_raw)`, accepting a few additional shapes.
- The base schema contains eligibility already, so the original `CREATE
  TABLE IF NOT EXISTS` routine is not run.
- SQLite cache rows are stored separately from case transactions. Test cases
  assert that malformed/missing language fixtures leave **no cache or cases**.
- This remains a testing adapter. Actual GitHub repository eligibility may
  depend on rate-limit, inaccessible language data and the historical query
  surface; none of those are implied to be reproduced.

## Tests

`tests/test_miner_offline_repo_eligibility.py` contains **27** new tests:
threshold boundaries, order of rejection reasons, zero and negative language
byte handling, capitalization, cache hit and threshold invalidation, explicit
refresh, fallback repository GET, malformed/missing fixtures, SQLite rollback,
and integration with the offline PR→issue→case collector.

Local offline suite: **127/127 passing** (100 existing + 27 new).

```bash
python -m unittest discover -s tests -v
```

## Outstanding for full historical collector equivalence

- All branch-specific discovery/retrieval query modes and paging state.
- Original runtime caps and primary/high-yield worker-routing gates.
- Network-enabled GitHub client, rate-limit cache, and available credentials.
- Database runtime migrations and metadata provenance beyond the base schema.
- Scanner jobs/Slurm workers/UI and exact frozen output comparison.

Do not merge the draft branch until the integration gates are reviewed.
