# Wide-first v2 hotfix

This build addresses the issue where wide-first retrieval still produced many `repo_filter`, `repo_query_cap`, and `repo_cap_reached` exclusions but few/no valid cases.

Changes:

- Raises default base query to `stars:>=200`, Jan 2025 cutoff, `in:title,body`.
- Keeps repo-walk disabled; retrieval remains targeted PR search.
- Keeps high-precision stream terms and removes noisy `"fix #"`.
- Disables the hard per-pass raw-hit repo cap by default (`max_raw_hits_per_repo_per_pass: 0`).
- Raises `max_processed_prs_per_repo` to 50 so repo diversity does not block validation too early.
- Makes primary-language filtering soft by default: GitHub search still asks for `language:Python`, but API primary-language mismatch no longer hard-excludes a PR before behavior-file validation.
- Uses query phase order: single stream -> issue-link baseline -> combined issue-link + stream.
- Enforces `targeted_max_pages_total` in pagination.
- Replays old capped/exhausted retrieval rows on `make ensure-db` so existing DBs are not stuck with cap-heavy outcomes.

Tests:

- `python -m compileall -q ui src tests`
- `PYTHONPATH=$PWD pytest -q` -> 77 passed, 1 skipped
- `PYTHONPATH=$PWD python scripts/test_dependency_downgrade.py` -> OK; OSV skipped only because `osv-scanner` is not installed in the test container.
