# Minimum issue body + active repo seed fix

This build improves the downstream-first collector after the first live run only produced a few cases.

## Changes

- `ISSUE_MIN_BODY_CHARS ?= 200` default added. One-line/underdescribed issues are excluded with `issue_body_too_short`.
- `EXCLUDE_DOCS_SCOPE_ONLY ?= true` default added. Documentation-only changes such as `docs/conf.py` are excluded with `docs_only_change` unless the PR also touches source/dependency/CI artifacts.
- `ACTIVE_REPO_SEED ?= true` default added. The collector runs one structural, keyword-free global PR search over the lookback window to seed repositories that actually have merged issue-linked PR activity. Candidate construction remains repo-scoped.
- `REPO_SAMPLE_STRATEGY ?= active_first` default added. Active seed repos are processed first; the star-band repo universe still tops up coverage.
- Collection diagnostics now log new cases, new exclusions, and top exclusion reasons at the end of structural collection.
- Upstream feature extraction now records issue body chars/words, code block chars, largest code block size, code-heavy flag, and high-context-load flag. These are recorded as features, not used as retrieval keyword filters.

## Recommended run

```bash
make reset-db
make collect RETRIEVAL_MODE=repo_window_pr_search MAX_REPOS=50 LOOKBACK_MONTHS=12 MAX_CASES=200 MAX_CASES_PER_REPO=3 ISSUE_MIN_BODY_CHARS=200 RANDOM_SEED=42
```

For quick debugging:

```bash
make reset-db
make collect RETRIEVAL_MODE=repo_window_pr_search MAX_REPOS=20 LOOKBACK_MONTHS=12 MAX_CASES=100 MAX_CASES_PER_REPO=2 ISSUE_MIN_BODY_CHARS=200 RANDOM_SEED=42
```

## Why this should produce more cases

The old repo-universe sample could pick many active Python repositories that had no issue-linked merged PRs in the target window. The active seed is structural and keyword-free: it only finds repos that already have `is:pr is:merged linked:issue` hits, then the normal same-repo/tool-applicable validation runs.
