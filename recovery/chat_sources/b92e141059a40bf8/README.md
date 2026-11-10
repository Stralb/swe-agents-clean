# Malicious Issue Miner

A downstream-evidence-first GitHub mining system for studying potentially malicious or security-relevant GitHub issues that are linked to merged downstream PRs.

The study object is:

```text
GitHub issue -> same-repo linked merged PR -> downstream code/config/dependency/CI evidence
```

The miner intentionally does **not** use issue keywords such as `bug`, `traceback`, `security`, `dependency`, or `CVE` as main inclusion filters. Those words are extracted later as upstream indicators after a case has entered the downstream-evidence frame.

## Current methodology

The main pipeline is:

```text
1. Build a repository universe
2. Search each repo/month for merged PRs linked to issues
3. Hydrate PRs with GraphQL/REST metadata
4. Keep only same-repo issue-linked PRs
5. Route candidates to approved downstream workers by tool applicability
6. Run CodeQL / Gitleaks / OSV / dependency downgrade detection
7. Extract upstream issue indicators after inclusion
8. Review only downstream findings or blocked scans
```

### Repository universe

The default repository frame is objective and reproducible:

```text
public GitHub repository
primary language = Python
stars >= 200
archived = false
fork = false
recently pushed
issues enabled
```

Repository discovery is split by star bands so a single global GitHub search page does not define the sample:

```text
language:Python stars:200..499 archived:false fork:false pushed:>=2024-01-01
language:Python stars:500..999 archived:false fork:false pushed:>=2024-01-01
language:Python stars:1000..4999 archived:false fork:false pushed:>=2024-01-01
language:Python stars:5000..9999 archived:false fork:false pushed:>=2024-01-01
language:Python stars:>=10000 archived:false fork:false pushed:>=2024-01-01
```

### Candidate retrieval

For each repo and month, the structural PR query is:

```text
repo:OWNER/REPO is:pr is:merged linked:issue draft:false merged:YYYY-MM-01..YYYY-MM+1-01 -author:dependabot[bot] -author:renovate[bot] -author:github-actions[bot] -author:pre-commit-ci[bot] -author:mergify[bot]
```

This query is PR-first and downstream-first: it finds landed PRs, then attaches the upstream issue.

### Mechanical inclusion rule

A PR becomes a case only when all of these are true:

```text
PR is merged
linked issue exists
linked issue repository == PR repository
PR author is not a maintenance bot
at least one approved downstream worker is applicable
```

This is a deterministic eligibility rule, not a score and not issue-quality validation.

### Downstream workers

Approved downstream workers are:

| Worker | Starts when | Output examples |
|---|---|---|
| `codeql` | a changed file ends with `.py` or `.pyi` | `codeql_alert_introduced`, `codeql_no_new_alert`, `not_applicable:no_python_files_changed` |
| `secret_ci` | a PR patch has added lines / checkout is available | `secret_introduced`, `secret_scan_failed`, `not_applicable:no_added_patch_lines` |
| `osv_dependency` | a dependency manifest/lock file changed | `osv_vulnerability_introduced`, `osv_no_change`, `not_applicable:no_dependency_files_changed` |
| `dependency_downgrade` | a dependency manifest/lock file changed | `dependency_downgraded`, `constraint_relaxed`, `pin_removed`, `not_applicable:no_dependency_files_changed` |

Dependency files include:

```text
requirements.txt
requirements/*.txt
requirements.in
dev-requirements.txt
test-requirements.txt
pyproject.toml
setup.py
setup.cfg
Pipfile
Pipfile.lock
poetry.lock
uv.lock
pdm.lock
environment.yml
environment.yaml
conda.yml
conda.yaml
tox.ini
```

### Upstream indicators

After a case is included, the miner extracts issue-side indicators such as:

```text
traceback / stack trace
steps to reproduce / minimal repro
expected vs actual behavior
failing test
security wording
CVE/security regression wording
dependency/version wording
CI/secrets wording
AI-agent mentions
issue length, code-block count, comment count, labels, assignees, author association
```

These are features for analysis and UI review, not inclusion filters.

## Install

```bash
make install
make init-db
make tools
```

Put a GitHub token in `.env`:

```bash
GH_TOKEN=your_token_here
```

Then verify:

```bash
make verify-github
```

## Main commands

```bash
make collect MAX_CASES=500
make scan MODE=full MAX_CASES=500
make ui
```

`MODE=full` runs the approved downstream workers and gradually includes CodeQL. `MODE=fast` skips CodeQL.

## Recommended research run

```bash
make reset-db
make collect RETRIEVAL_MODE=repo_month_pr_search MAX_REPOS=50 MAX_CASES=500 MAX_CASES_PER_REPO=10 LOOKBACK_MONTHS=12 RANDOM_SEED=42
make scan MODE=fast MAX_CASES=500
make scan MODE=full MAX_CASES=500 CODEQL_TRIGGER=all_python CODEQL_MAX_PER_RUN=3
make ui
```

## Parallel and cluster execution

The miner is designed to split cleanly by repository and month.

### Repository/month sharding

Use these environment variables to partition mining work across cluster nodes:

```bash
REPO_SHARD_COUNT=8 REPO_SHARD_INDEX=0 MONTH_SHARD_COUNT=1 MONTH_SHARD_INDEX=0 make mine
REPO_SHARD_COUNT=8 REPO_SHARD_INDEX=1 MONTH_SHARD_COUNT=1 MONTH_SHARD_INDEX=0 make mine
...
REPO_SHARD_COUNT=8 REPO_SHARD_INDEX=7 MONTH_SHARD_COUNT=1 MONTH_SHARD_INDEX=0 make mine
```

Or shard by month as well:

```bash
REPO_SHARD_COUNT=4 REPO_SHARD_INDEX=0 MONTH_SHARD_COUNT=3 MONTH_SHARD_INDEX=0 make mine
REPO_SHARD_COUNT=4 REPO_SHARD_INDEX=0 MONTH_SHARD_COUNT=3 MONTH_SHARD_INDEX=1 make mine
REPO_SHARD_COUNT=4 REPO_SHARD_INDEX=0 MONTH_SHARD_COUNT=3 MONTH_SHARD_INDEX=2 make mine
```

Sharding is deterministic using a stable hash, so the same repo/month is assigned to the same shard.

### Scanner workers

The scanner queue is persisted in SQLite and claims jobs atomically. You can scale evaluator workers by worker family:

```bash
make evaluate-cheap SECRET_WORKERS=4 DEP_WORKERS=4 SOURCE_WORKERS=0 CODEQL_WORKERS=0
make evaluate-codeql CODEQL_WORKERS=2
```

For multi-node clusters, use either:

1. one shared database on reliable shared storage that supports SQLite locking, or
2. separate DBs per repo/month shard and merge/export results after the run.

The second option is safer on clusters where NFS/parallel filesystems do not reliably support SQLite write locking.

## UI

The default Streamlit UI now uses the private Hugging Face Parquet research snapshot:

```bash
make install
hf auth login
make ui
```

Or put a Hugging Face read token in `.env`:

```text
UI_DATA_BACKEND=parquet
HF_DATASET_REPO=Stralb/malicious-issue-miner-data
HF_DATASET_REVISION=main
HF_TOKEN=your_huggingface_read_token_here
```

The Parquet UI downloads only the small hot research files into the standard Hugging Face cache and queries them locally with DuckDB. The large excluded-case detail payload remains remote and is located through `excluded_case_route.parquet`, so a detail request opens only the matching Parquet shard. PR patch shards are cached lazily on first patch use.

Parquet mode provides:

- fast overview metrics and research summaries
- paginated/filterable case review
- local-cached issue/PR bodies and finding evidence
- scanner and pattern insights
- excluded-case browsing with routed remote detail reads
- changed-file browsing and lazy patch caching

The Hugging Face research snapshot is **read-only**. Manual labels/tags are not written back to the dataset.

For the legacy/live SQLite control-plane UI, use:

```bash
make ui-sqlite
```

SQLite mode retains runtime panels, worker state, logs, mutable tags/labels, and database exports.

Colors in the UI mean **review state / downstream worker evidence**, not candidate scores.

## Case and scanner states

Every scanner job ends in exactly one outcome:

```text
ok
finding
not_applicable + reason
error
timeout
```

A case ends in one of:

| State | Meaning |
|---|---|
| `scanner_running` | at least one applicable worker is still pending/running |
| `scanned_clean` | all applicable workers completed without findings and all non-applicable workers have explicit reasons |
| `needs_review` | at least one downstream worker produced a finding |
| `scan_blocked` | a required applicable worker failed/timed out and confidence is blocked |

A clean scanner result is recorded as “no tool finding”, not “safe.” CodeQL, OSV, and secrets scanners provide downstream evidence, not proof of absence of maliciousness.

## Status and exports

```bash
make status
make export
```

Exports include the database, config, and methodology snapshot for reproducibility.

## Tests

```bash
make self-test
# or
PYTHONPATH=. pytest -q
```

The test suite covers repository/month query construction, deterministic sharding, tool-applicability routing, scanner job states, dependency downgrade detection, CodeQL delta-linking, Gitleaks contexts, UI indicator rendering, and migration/backfill behavior.
