# Miner reconstruction — offline PR → issue → case persistence

**Scope:** engineering recovery and reproducible software integration. **No new research, no live mining, no scanner runs, no Wits cluster operations.**

## Result

`src/pipeline/offline_case_collection.py` connects the already-consolidated, byte-preserved miner helpers to the original 11,380-byte SQLite base schema. A deliberately fail-closed `ReplayGitHubClient` supplies synthetic GitHub PR, changed-file, and issue responses; `open_ephemeral_database()` supplies an in-memory database. No historical entrypoint is imported or executed.

The new adapter accepts one explicit `FixtureCollectionPolicy`, reads all required fixture responses, classifies a PR, resolves same-repository issues, and commits the accepted records in **one SQLite transaction**. Original table names and most affected field mappings are preserved: `repos`, `pull_requests`, `pr_files`, `issues`, `issue_pr_links`, `upstream_features`, `cases`, `ai_markers` and `excluded_cases`. The case status is `metadata_collected`; no `scanner_jobs` are created.

### Preserved semantics

- Reject disallowed unmerged/merged PRs, maintenance bots, clearly non-behaviour-only and documentation-scope changes.
- Apply optional JavaScript/TypeScript changed-file requirement; enforce explicit changed-file and multi-issue caps.
- Accept closing-keyword and same-repo title/body/head issue references using **original** `issue_linker` source.
- Validate referenced issues, original word-count/English gate, issue body length, explicit AI marker requirements, and `upstream_features` extraction.
- Preserve the original repo/issue/PR/case primary relations, issue-link methods, AI cohort values and metadata column names.
- Use SQLite transaction rollback to avoid half-written case metadata on failure.

### Explicit differences from the historical miner

- This is a **new, partial** fixture path. It does *not* call the 3,000-line historical `collect_pipeline._process_pr` or the historical `Database` class.
- The original collector uses separate nested writes. This adapter batches accepted database records into a single transaction and reruns are idempotent for `ai_markers` (deletes and re-inserts per case). Original code can append duplicate marker records on repeated case processing.
- The test adapter requires HTTPS fixture URLs, rejects mismatched issue/PR numbers, checks repo names and refuses file-backed/attached SQLite connections.
- Comment-message and commit-message issue-link fallbacks, GraphQL-prefetched links, and AI markers from commit messages are not replayed.
- No historical lookback checks, caps on total cases/time or per-repository cases, repository eligibility, primary-worker or high-yield routing gates have been implemented in this partial path.
- No Github Search acquisition, remote API sessions, file-cache/SQLite lock handling, scanner routes, distributed workers or Slurm integration.
- `langdetect` may change original English classification when installed; offline tests pin the fallback explicitly where needed. Production dependency versions are not yet locked.

These missing paths are **not evidence that the original miner can already be reproduced end to end**. This is one tested seam between recovered filters, fixture API responses and frozen base DDL.

## Verification

The **28 new** synthetic cases in `tests/test_miner_offline_case_collection.py` cover accepted case persistence, source statuses and features, excluded decisions, issue/PR identity mismatches, missing fixtures, HTTP 404/422/500 behavior, docs/JS/AI/body gates, multi-issue cases, safe SQL rollback on an injected trigger failure, and rejection of attached SQLite databases. The existing 37 tests in the standalone stage remain green: **65/65** passed locally (Python 3.13). The repository CI separately tests against Python 3.11.

```bash
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

The synthetic tests do not open historical Wits paths, contact GitHub, construct real scanners, or modify cluster data.

## Next engineering gates

1. Restore the original collector's explicit lookback/eligibility/applicability checks as separately testable predicates with hash-backed source provenance.
2. Replay acquisition paths from the recovered 3,000-line collector, beginning with source-preserving refactors and bounded GitHub Search fixtures.
3. Extract historical `Database` migration and concurrency behavior into a disposable SQLite filesystem test, with a strict create-new-path guard and no reference to Wits.
4. Reconstruct runtime dependency versions and scanner setup in a disposable environment, then verify a full **historical** pipeline against its original, frozen outputs.

**The source snapshots remain immutable, the PR stays draft, and `main` remains unchanged.**
