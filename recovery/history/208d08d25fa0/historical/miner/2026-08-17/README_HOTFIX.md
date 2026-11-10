# Downstream-first methodology upgrade

This version changes the miner from issue-keyword-first retrieval to repo/month PR-first retrieval.

Main changes:

- Primary collection now uses repo-scoped merged PR searches with `linked:issue`.
- GraphQL/REST hydration verifies same-repo issue links and changed-file applicability.
- Main inclusion no longer depends on issue keywords, issue quality, or high-intent buckets.
- Approved downstream workers are CodeQL, Gitleaks, OSV, and dependency downgrade detection.
- Semgrep and custom patch-pattern scanning are not part of the trusted default pipeline.
- Scanner jobs now record route reasons, so the UI can show why each downstream worker ran or was not applicable.
- Repository and month sharding are available through `REPO_SHARD_*` and `MONTH_SHARD_*` environment variables for cluster deployment.

Tests: run `PYTHONPATH=. pytest -q`.
