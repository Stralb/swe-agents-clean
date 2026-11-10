# Collector lookback and repository-universe gates — offline reconstruction

**Scope:** engineering recovery and deterministic test fixtures only. No network
collection, Wits access, new research experiment, or historical-output reclassification.

## Exact source basis

Historical implementation: `historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py`,
SHA-256 `5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750`.
Original source regions include `_lookback_months` (lines 366–372),
`_lookback_start` (375–386), `_iso_dt` (389–395),
`_within_lookback` (398–407), `_repo_passes_universe` (2167–2178),
and the `_process_pr` PR and issue gates (616–881).

The original code was **not imported or executed** by this change. We
statically inspected its implementation, then checked a separately written
pure adapter against synthetic examples.

## Implemented

- `src/pipeline/collector_gates.py`: original-style repository screen
  (`archived`, `fork`, threshold stars, disabled issues) in original order.
  Includes the original `configured_min_stars or 200` fallback.
- Original config lookback-month parsing: nonpositive/invalid -> unset.
- Start-date precedence: `collection.lookback_start` takes priority over
  positive `lookback_months`.
- Original relative cutoff: `months × 31 × 24 × 60 × 60` seconds.
- Original missing/invalid *event* timestamps count as within lookback.
- Inclusive cutoff comparison; event `Z` offsets and explicit time zones.
- Original PR selection: merged date unless
  `require_pr_merged_after_lookback` is disabled, in which case
  merged -> closed -> updated -> created.
- Original issue selection: created date unless
  `require_issue_created_after_lookback` is disabled, in which case
  closed -> updated -> created.
- Original exclusion codes `outside_lookback_pr` and
  `outside_lookback_issue` routed into the disposable `excluded_cases` table.

These options are **opt-in** on `FixtureCollectionPolicy`; defaults are left
disabled so earlier offline fixture tests remain compatible. The repository
screen is separate from the historical JS/TS language-bytes eligibility gate,
which still depends on cached database state and external API requests.

## Intentionally strict reconstruction differences

1. The historical relative month cutoff calls `datetime.now(timezone.utc)`
   from the process clock. The new adapter requires the caller to supply an
   explicit *aware* `reference_now_utc`. This keeps tests deterministic.
2. The historical `_iso_dt()` returns naive event datetimes unchanged, so its
   `.timestamp()` uses the host machine's local time zone. The offline adapter
   instead **refuses** a naive event datetime when a comparison is needed.
   Tests must provide a timezone offset, not guess Wits' historical timezone.
3. The original repository-universe filter is used in specific upstream
   search paths; enabling it universally would modify discovery semantics.
   It therefore requires `enforce_repo_universe=True` in synthetic replay.
4. Our adapter stores an exclusion reason in the in-memory test DB on a
   repository screening failure, whereas the original outer collection loop
   has different logging paths. This does not purport to reproduce the
   exact historical exclusion log count.

## Tests

`tests/test_miner_collector_gates.py` adds 25 tests. They check historical
31-day-month arithmetic, date fallback precedence, permissive missing/invalid
timestamps, clock injection, explicit timezone semantics, repository-filter
order, early rejects before fixture fetches, accepted persisted cases, and
read-only AST presence checks against the frozen original collector.

Local fixture-suite status: **100 tests passed** (75 existing + 25 new).

```bash
python -m unittest discover -s tests -v
```

## Outstanding for end-to-end miner reproduction

- Historical `repo_eligibility` JS/TS byte-share rule and its cache.
- Worker applicability and high-yield gates (original routing-key mismatch is
  separately documented and must not be silently changed).
- Historical runtime `max_cases`, `max_cases_per_repo`, max-seconds controls.
- Comment/commit/GraphQL issue-link fallback, rate-limited live GitHub client.
- Historic DB migration wrapper, scanner queue/Slurm and Streamlit UI.
- Independently measured equivalence to original frozen miner outputs.

**Do not merge the draft PR until these contracts are reviewed.**
