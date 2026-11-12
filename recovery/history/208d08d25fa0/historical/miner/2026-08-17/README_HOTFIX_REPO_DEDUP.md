# Repo de-dup / issue-linked retrieval hotfix

This build changes the live miner to stop wasting hours rediscovering the same repo/PR outcomes before any downstream evaluation can happen.

## Main changes

- Default retrieval phase order is now issue-linked first:
  1. `issue_link_baseline`
  2. `combined_issue_link_stream`
  3. `single_stream_high_signal`
- Broad single-stream search no longer runs first by default. Valid cases require a same-repo linked issue, so unlinked stream-only queries were mostly creating duplicates/no-linked exclusions.
- Per-query repo budget: default `max_prs_per_repo_per_query: 1`.
- Per-run new-PR repo budget: default `max_new_prs_per_repo_per_run: 2`.
- Single-stream fallback is limited to high-signal terms only.
- UI generated queries now show the issue-link+stream query as the primary query for stream terms.

## Validation rules retained

A PR still only becomes a valid case if it has a same-repo linked issue, PR merged after 2025-01-01, issue created after 2025-01-01, repo constraints, behaviour-changing files, and issue-level filters.

## Tests

- `python -m compileall -q ui src tests`
- `PYTHONPATH=$PWD pytest -q` -> 79 passed, 1 skipped
- `PYTHONPATH=$PWD python scripts/test_dependency_downgrade.py` -> OK, OSV skipped because tool absent in container
