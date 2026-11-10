# Historical retrieval dispatch and search/pagination replay

**Engineering reconstruction only.** This does not run the production miner, execute a scanner, contact GitHub, submit a Slurm job, or alter the Wits database or any original research result.

## Exact historical source

All code extracted for this test stage comes from the unchanged `historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py`, whose SHA-256 is `5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750`. The exact source bytes match the August 17 and August 19 snapshots in the recovery branch.

`tests/support/archived_collection_contract.py` validates that checksum, selects only allowlisted AST function definitions, compiles those definitions in a **test-only, isolated namespace**, and injects only inert constructors or in-memory response fixtures. It does **not** import or execute the historical module's top-level code. Any source revision needs an explicit new checksum review, not a silent fallback.

## What the tests now execute

| Area | Historical code under test | Safety boundary | Verified behaviour |
| --- | --- | --- | --- |
| Dispatch | `collect()` | `Database` and `GitHubClient` constructors replaced by refusing stubs; collection handlers replaced by spies | All `repo_month`, targeted, AI-only/hybrid and repo-walk branches; alias precedence, case-count forwarding, hybrid budget short-circuit, cache/cooldown constructor arguments |
| Date-window search | `_github_search_timestamp`, `_parse_agentic_lookback`, `_bounded_merged_query`, `_split_agentic_window`, `_iter_adaptive_agentic_search` | `FixtureSearchOnly`, wrapping `ReplayGitHubClient`; unrecorded requests raise `IncompleteReplayError` | Count probe reused as page 1, page 2 continuation, chronological recursive splitting, max-depth and one-second failure, disabled legacy mode, empty/future ranges |
| Targeted collection | `_collect_targeted_stream_search` plus exact query builders, visible-outcome counters and retrieval-record functions | Fixture-only GitHub plus the original `Database` running inside `disposable_original_database()` | Query order, persisted `next_page`/`exhausted`, partial/empty/full pages, cap exhaustion, 500 errors and retries, 1,000-result 422 boundary, missing fixture abort |
| Full synthetic case | Exact targeted query -> exact historical `_process_pr` -> original DB methods | Newly created disposable SQLite and synthetic PR/repo/issue/file fixtures | `cases` and `case_retrievals` populated; two streams can link to the same case without inserting extra AI marker rows within one targeted run |

### Historical behaviours identified and frozen by tests

1. **Seven-day pre-split overlap.** `_iter_adaptive_agentic_search` uses inclusive `merged:start..end` qualifiers, but starts each next seven-day chunk **at** the previous chunk's end, without adding a second. A synthetic PR exactly at that boundary appears twice. The binary split helper `_split_agentic_window` correctly advances right-hand windows by one second; this is specifically a **pre-split** difference. Live duplicate frequency has not been measured.
2. **Statistics reset across initial chunks.** The recursive function runs `stats.update({ ...: 0 })` on every seven-day chunk. When a caller shares the dictionary, counters after the call describe only the **final** chunk in the synthetic test, not all earlier chunks. The source is preserved unchanged; earlier historical reported counts should not be retrospectively "corrected" without an explicit reconstruction version.
3. **Resumed targeted query state.** `next_page` records the page after the last fetched page, even when a short page causes `exhausted=1`. An empty page leaves `next_page` where it was and also marks exhausted. A 500 search error retains a retryable cursor and `status=error`; a 1,000-result-window 422 is treated as an exhausted search window.
4. **Case-level deduplication differs by entrypoint.** A standalone re-run of historical `_process_pr` can duplicate `ai_markers` rows; the original targeted-stream collector avoids reprocessing previously visible outcomes across retrieval queries. These are separate original behaviours and both are now verified on synthetic data.
5. **Historical query coverage limitations remain.** The tests prove the original generator's control flow, **not** GitHub Search's current indexing behaviour or completeness, not the empirical 3,809-workflow results, and not a complete miner run.

### Coverage not yet claimed

- The full `collect()` function with **real original** collector handlers running together. Dispatch tests use stubs by design; targeted tests invoke that handler independently.
- The historical `repo_month`/downstream-first retrieval orchestration, actual GitHub Search rate limits, secondary cooldown/retry, persisted network caching, GraphQL prefetching, cross-worker coordination and source repository clones.
- Any scanner/CodeQL/OSV/Gitleaks/Trivy stage, job/worker/scheduler execution, Streamlit UI behaviour, frozen historic study output replication or all research-stage scripts.

### Re-run locally

Run from a checkout containing the entire recovery history:

```bash
python -m unittest tests.test_miner_archived_search_dispatch -v
python -m unittest tests.test_miner_archived_targeted_resume -v
python -m unittest discover -s tests -v
```

This stage adds **37 tests**, all passing locally together with the previous suite (**205 tests total, Python 3.13**). CI executes the same tests with its configured Python version after commit. The original historical files and GitHub `main` remain unchanged, and the PR stays a draft.
