# Exact historical PR-processing replay in a disposable environment

**Purpose:** reconstruct the existing miner's software behaviour, not conduct a new scientific experiment. **Scope:** one historical `_process_pr` call, not the entire `collect()` workflow.

## Verified source identity

- Historical source: `historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py`.
- SHA-256: `5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750`.
- The same source hash is verified in the August 17, August 19 and October 20 snapshots. The historical files are never modified.
- `tests/support/archived_pr_contract.py` parses the archived source and compiles an explicit allowlist of **ten function definitions** only: `_process_pr`, `_safe_commit_messages`, `_store_upstream_features`, `_lookback_months`, `_lookback_start`, `_iso_dt`, `_within_lookback`, `_lookback_description`, `_min_issue_body_chars`, and `_issue_body_char_count`.
- It does **not import** the historical collector module or execute its top-level imports, `collect()`, Slurm orchestration, scanner execution, or CLI.

## Isolation constraints

The runner checks the caller before invoking historical code. It accepts **only** the new `FixtureOnlyGitHub` wrapper over `ReplayGitHubClient` and an initialized `Database` located under `disposable_original_database()`'s temporary directory. The wrapper turns missing fixture responses into an unconditional `IncompleteReplayError` instead of allowing the historical broad `except Exception` blocks to misclassify an incomplete replay as an exclusion. No real credentials, network client, or original Wits database path are accepted.

The original function **does write** to its supplied disposable SQLite database. It is not read-only and not atomic, and must not be used on historical data. These controls are for trusted, locally recovered source and synthetic fixtures only; they are not a general-purpose Python sandbox.

## Directly exercised historical gates

Tests in `tests/test_miner_archived_pr_contract.py` run the **original source function** with synthetic PRs, issues, changed files, and commit/comment pages:

| Gate / contract | Verified behaviour |
| --- | --- |
| SHA-256 and source identity | All three snapshot source hashes match; altered source fails before compilation |
| Positive fixture | Original creates repository, PR, issue, changed-file, link, feature, marker, and case records |
| Comparison with new fixture adapter | One accepted case has the same table counts and AI-cohort label |
| JS/TS surface / documentation | The JS/TS surface exclusion runs **before** the general non-behavioural file exclusion; documentation-only PRs can also be rejected by the later filter if JS/TS gating is off |
| PR lookback and linked-issue lookback | Exclusion reasons and write order verified using fixed ISO-8601 dates and explicit `lookback_start` |
| Missing/invalid API responses | 422 PR-file error and 404/500 issue errors follow original exclusion paths; absent fixture keys fail closed in the harness |
| Linked issues | Comment and commit-message fallbacks, duplicate link de-duplication, prefetched multi-issue exclusion |
| Evidence requirements | Body-character default of 200, issue word-count quality filter, changed-file cap |
| Collection caps | Maximum cases and per-repository caps take effect **after** saving PR metadata |
| Replays | Case upsert remains unique, but marker inserts are repeated |
| Worker route | Prior standalone routing tests preserve the missing `ci_security` key; this direct handler test confirms earlier filters can reject documentation before routing |

## Important compatibility differences discovered

1. **Non-atomic historical persistence.** The old `_process_pr` saves repository, PR, and changed-file metadata before fetching the linked issue. A 404, an older issue, a low-quality body, a case-cap, or an interrupted fixture may leave those earlier rows present. Our new `collect_fixture_pr` validates its fixture inputs before a single transaction instead. The two are not byte-for-byte equivalent in failure cases.
2. **Duplicate AI markers on replay.** The historical `create_or_get_case` upserts a case, but the subsequent marker inserts have no de-duplication check. Replaying the same PR/issue twice leaves one case and two AI-marker rows. The newer fixture adapter does not duplicate them. **Do not silently rewrite historical evidence**; evaluate a separately versioned fix when full pipeline tests are available.
3. **Missing fixture handling.** The historical function catches broad `Exception` for issue and PR-file requests. Our testing-only wrapper raises a non-`Exception` abort for absent fixtures, avoiding a false `pr_files_unavailable` or `inaccessible_issue` classification.
4. **Date semantics and source defaults.** With lookback enabled, the source uses a 31-day approximation for each month and accepts missing or malformed timestamps. The historical issue-body minimum defaults to **200 characters** unless explicitly configured. Tests set an absolute lookback start to avoid the original wall clock.
5. **Original worker routing key mismatch.** The separately recorded `ci_security`/`secret_ci` mismatch remains in the byte-preserved functions. Nothing in these tests authorizes changing the cohort-selection logic.

## Boundaries and next steps

This stage **does not yet** exercise `collect()` retrieval-mode dispatch, GitHub Search adaptive window splitting, duplicate discovery across streams, full repository eligibility persistence, GraphQL hydration, live retry/cooldown/cache, original settings initialization, cluster workers, scanners, Streamlit UI, or historical-output replication. Tests are **software-fixture contracts**, not independent validation of research counts.

The next engineering task is to replay actual original *retrieval-mode dispatch* over explicit search-page fixtures, with the same restricted GitHub transport and disposable schema. The source files and frozen Wits data must remain unchanged.

## Test commands

```bash
python -m unittest tests.test_miner_archived_pr_contract -v
python -m unittest discover -s tests -v
```

The focused test module contains 26 unit/integration tests, including two tests that explicitly document divergences from the new adapter. The full local suite is expected to pass without credentials, live GitHub APIs, Wits access, scanners, or a persistent SQLite database.
