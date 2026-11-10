# Archived repo-month / repo-window exploit-lane integration (offline)

## Historical code executed

All functions are AST-extracted from the immutable, SHA-256-verified historical `collect_pipeline.py` (`5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750`). The test harness executes the original **`collect()` dispatcher → `_collect_repo_month_pr_search()` → `_process_structural_pr_search()` → `_process_pr()`** in that order. No active replacement collector or modified historical function is used.

The fixture reproduces the **exploit lane** using a synthetic existing-repository seed. `MINING_REPO_SEED_DB` is always a literal non-file sentinel and `load_existing_repo_seed_names` is a refusing, in-memory fixture provider. Other lanes (`explore`, `mixed`), external seed DB files, global live discovery and GraphQL hydration are not claimed.

The original `Database` is initialized only in the existing `disposable_original_database()` harness. A replay-only `FixtureStructuralGitHub` supplies closed PR lists, repository metadata and PR/issue/file responses through an exact-match in-memory transport; missing fixtures terminate replay. Both live APIs and scanner/worker execution are impossible in this harness.

## Synthetic contract coverage

- A fixed 2026-10 month stratum, one seeded repository, one merged PR and one same-repository linked issue pass through all original functions to `cases`, `pr_files`, `issue_pr_links`, `ai_markers` and `case_retrievals`.
- `downstream_first` selects the original repo-window branch, not the targeted-search branch.
- Archive, star-count and draft/merge-window exclusions occur before downstream PR hydration; negative cases cannot silently count as case creation.
- **Historical `max_repos=1` interaction:** The repo-month handler increments `repo_count` before entering its month loop and then calls `_limit_reached()` with that updated count. With `max_repos=1`, it skips the first repository's month altogether even though the repository was accepted. Our normal single-repository fixture uses `max_repos=2`, and a separate test freezes the original `max_repos=1` behaviour. This is not silently patched.
- Missing HTTP fixtures, real credential strings, caller-supplied DB paths, GraphQL requirements, and exploration lanes fail closed.

## Non-equivalence and remaining work

This proves a **single synthetic structural repo-month path**, not full live reproduction. No GitHub indexing, distributed seed DB, scanner-side tool validity, workload scheduling, full repo sampling/partitioning, frozen result cohort or Streamlit UI is reproduced. The real original collector's stateful migrations can modify stored data; tests use only freshly disposable SQLite files.

The original month-window routine has historical date semantics. We do not reinterpret or correct it.

Verification: `python -m unittest tests.test_miner_connected_repo_month_dispatch -v`, then `python -m unittest discover -s tests -v`.
