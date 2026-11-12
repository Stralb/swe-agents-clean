# Next iteration retrieval hotfix

This build changes the miner from a noisy/deep crawler into a wide-first targeted PR-search scheduler.

## Retrieval design

- Base query now uses `stars:>=200` and `merged:>=2025-01-01`.
- Repo-walk is disabled by default (`repo_walk_enabled: false`).
- Default retrieval mode is `targeted_pr_search`.
- Query phases run in this order:
  1. `single_stream` — search each stream term by itself first.
  2. `combined_issue_link_stream` — then search issue-link + stream term combinations.
  3. `issue_link_baseline` — then broad issue-link-only baseline.
- Query scheduling is round-robin across streams so the miner does not get stuck in one stream or one repo class.
- The default terms remove broad noisy terms such as `"fix #"`, `"auth"`, `"token"`, `"CI"`, `"env"`, `"workflow"`, `"dependency"`, `"dependencies"`, `"validation"`, `"edge case"`, and `"test case"`.
- High-precision dependency/CI/source/security terms are used instead.

## Diversity controls

- `max_cases_per_repo: 3`
- `max_processed_prs_per_repo: 10`
- `max_raw_hits_per_repo_per_pass: 5`
- `targeted_per_page: 20`
- `targeted_max_pages: 1`

Each GitHub hit is accounted for as processed, duplicate, repo-filtered, excluded, or case-linked. Silent drops should not occur.

## Date rules

- PR must be merged on/after `2025-01-01`.
- Linked issue must be created on/after `2025-01-01`.
- Old issues updated in 2025 do not pass unless their `created_at` is also in range.

## Scanner rule retained

Every valid case still gets scanner jobs for source-code, dependency, secret/CI, and CodeQL. Clean requires all required scanner jobs to reach a final state and no introduced findings.
