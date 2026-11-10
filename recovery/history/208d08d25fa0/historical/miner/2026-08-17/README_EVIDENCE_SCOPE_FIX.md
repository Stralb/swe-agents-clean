# Evidence Scope Fix

This iteration tightens candidate construction so the miner stops producing cases that are structurally valid but weak as downstream evidence.

## Problem found from exported cases

The exported bundle showed three main problems:

1. **CodeQL was not running for JS/TS in the exported run** because the run used `CODEQL_TRIGGER=all_python`. The Makefile default is now `all_codeql`; do not override it to `all_python` for the multi-language study.
2. **A single broad PR was creating multiple cases** because it had multiple linked issues. This is weak causal evidence: one huge PR cannot be cleanly attributed to one issue description.
3. **Very large/batch PRs and generic UI/source changes were being accepted as evidence candidates** even though they are unlikely to produce useful downstream evidence quickly.

## New defaults

```makefile
CODEQL_TRIGGER ?= all_codeql
CODEQL_LANGUAGE ?= auto
REQUIRE_PRIMARY_WORKER ?= true
REQUIRE_HIGH_YIELD_SURFACE ?= true
MAX_CHANGED_FILES_FOR_EVIDENCE ?= 75
MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE ?= 1
```

## New exclusion reasons

- `ambiguous_multi_issue_pr`
  - PR has more linked issues than `MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE`.
  - Prevents duplicate weak cases from one broad PR.

- `pr_scope_too_large_for_evidence`
  - PR changed more than `MAX_CHANGED_FILES_FOR_EVIDENCE` files.
  - Prevents broad migrations / project rewrites from dominating evidence mining.

- `low_yield_downstream_surface`
  - PR has source changes but no dependency, CI/workflow, or security-sensitive source surface.
  - Avoids spending scans on generic UI/refactor changes that are observable but low-yield.

## What counts as high-yield downstream surface

The high-yield check uses downstream PR artifacts, not upstream issue keywords:

- dependency manifests / lock files
- CI/workflow/security config files
- CodeQL-supported source files in security-sensitive paths, such as auth, token, webhook, API routes, database, permissions, sessions, upload/download, Tauri/Electron, pairing/deeplink/QR flows
- source patches that add security-sensitive operations, such as token/env use, fetch/axios/request, SQL/database access, eval/exec/spawn, deserialization, validation/sanitization, secret references

## Recommended run

```bash
make reset-db
make collect \
  RETRIEVAL_MODE=repo_window_pr_search \
  MAX_REPOS=50 \
  LOOKBACK_MONTHS=12 \
  MAX_CASES=200 \
  MAX_CASES_PER_REPO=3 \
  ISSUE_MIN_BODY_CHARS=200 \
  REQUIRE_PRIMARY_WORKER=true \
  REQUIRE_HIGH_YIELD_SURFACE=true \
  MAX_CHANGED_FILES_FOR_EVIDENCE=75 \
  MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=1 \
  GITHUB_LANGUAGES=Python,JavaScript,TypeScript \
  RANDOM_SEED=42

make scan MODE=fast MAX_CASES=500
make scan MODE=full MAX_CASES=500 CODEQL_TRIGGER=all_codeql CODEQL_LANGUAGE=auto CODEQL_MAX_PER_RUN=3
```

## Important

`scanned_clean` means no approved scanner found introduced evidence under the configured workers. It does not prove the PR is safe. The goal of this iteration is to improve the candidate population before scanning.
