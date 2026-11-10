# Multi-language primary-worker fix

This iteration tightens the downstream-evidence-first methodology so the miner no longer accepts cases merely because a PR patch can be secret-scanned.

## Main changes

- Default discovery languages are now configurable with:

```bash
GITHUB_LANGUAGES=Python,JavaScript,TypeScript
```

- Repo seeding is still structural and keyword-free, but it now runs over the configured languages instead of Python only.
- Candidate inclusion now requires a **primary downstream worker** by default:

```bash
REQUIRE_PRIMARY_WORKER=true
```

Primary applicability means at least one of:

- CodeQL-supported source file changed (`.py`, `.js`, `.ts`, `.tsx`, `.rb`, `.go`, etc.)
- dependency manifest or lockfile changed (`pyproject.toml`, `package.json`, `pnpm-lock.yaml`, `go.mod`, etc.)
- CI/workflow/security config changed (`.github/workflows/*`, `Dockerfile`, `gitlab-ci.yml`, etc.)

Secret scanning still runs as an auxiliary worker for valid cases, but a random README/UI patch no longer qualifies just because it has added lines.

- Discovery mode no longer splits saturated repos by month by default. Busy repos are capped and skipped so collection stays wide-first.

```bash
REPO_WINDOW_EXHAUSTIVE_SPLIT=false
```

Use `REPO_WINDOW_EXHAUSTIVE_SPLIT=true` only for final exhaustive passes.

- CodeQL now auto-detects changed CodeQL-supported languages by default:

```bash
CODEQL_TRIGGER=all_codeql
CODEQL_LANGUAGE=auto
```

It runs base/head comparison per detected language and records compatibility aggregate runs (`codeql-base`, `codeql-head`, `codeql`) for the existing UI/scheduler.

## Recommended run

```bash
make reset-db
make collect RETRIEVAL_MODE=repo_window_pr_search MAX_REPOS=50 LOOKBACK_MONTHS=12 MAX_CASES=200 MAX_CASES_PER_REPO=3 ISSUE_MIN_BODY_CHARS=200 REQUIRE_PRIMARY_WORKER=true GITHUB_LANGUAGES=Python,JavaScript,TypeScript RANDOM_SEED=42
make scan MODE=fast MAX_CASES=500
make scan MODE=full MAX_CASES=500 CODEQL_TRIGGER=all_codeql CODEQL_LANGUAGE=auto CODEQL_MAX_PER_RUN=3
```

## Why this should produce better cases

The previous version allowed `patch available -> secret scan applicable -> candidate`, which admitted too many benign UI/docs cases. This version makes the candidate frame focus on places where downstream evidence is realistically measurable: source SAST, dependency regression, OSV vulnerability state, or CI/workflow/security config changes.
