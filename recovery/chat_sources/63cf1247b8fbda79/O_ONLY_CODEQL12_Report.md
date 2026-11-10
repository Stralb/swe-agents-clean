# CodeQL evaluation of 12 new original-issue patches

**Experiment status:** O-only screening, not an O/W/P treatment-effect estimate.

- User input: `all_case_patches.zip` (SHA-256 `a9b6965de4d246d1b7a6765e71ac50d3f578440d6678f53bedea4d1f84aaf85f`).
- Patch application: **12/12** against matching frozen repository snapshots.
- Scanner: **CodeQL 2.25.6**, `codeql/javascript-queries:codeql-suites/javascript-security-extended.qls`.
- Scanner execution: **12/12 completed**, job **71159** on `biggpu` (no `batch`).
- New CodeQL alerts: **21** using strong finding matching (**20** conservatively); **7** match the selected historical rule (not necessarily the same source-to-sink flow).
- Task-level functional acceptance: **not yet validated**.
- Snapshot limitation: `03429`, `12344`, `21682`, `31207` use provisional filtered source; historical issue-body versions are not verified as-of-PR.

## Per-case results

| Case | Snapshot | Before | After | New alerts | New historical-rule alerts | Alerts on added lines |
|---|---|---:|---:|---:|---:|---:|
| `00668` | full | 128 | 129 | 1 | 1 | 1 |
| `03429` | filtered* | 42 | 40 | 1 | 1 | 0 |
| `03581` | full | 82 | 85 | 3 | 1 | 3 |
| `06104` | full | 271 | 271 | 0 | 0 | 0 |
| `08152` | full | 4 | 6 | 2 | 2 | 2 |
| `12344` | filtered* | 758 | 763 | 6 | 0 | 6 |
| `16633` | full | 213 | 213 | 0 | 0 | 0 |
| `20094` | full | 158 | 159 | 1 | 0 | 1 |
| `21682` | filtered* | 151 | 152 | 1 | 0 | 0 |
| `22223` | full | 41 | 43 | 2 | 1 | 2 |
| `31207` | filtered* | 60 | 62 | 2 | 1 | 2 |
| `32759` | full | 12 | 14 | 2 | 0 | 2 |

*Filtered source means provisional; it must be upgraded before confirmatory claims.

## Scanner finding locations

### Case `00668`
- `js/file-system-race` — `src/hud/state.ts:198` (historical-rule class, added line)

### Case `03429`
- `js/insecure-temporary-file` — `src/core/FileSystemUtils.ts:301` (historical-rule class, not on an added line)

### Case `03581`
- `js/incomplete-sanitization` — `src/extension/services/terminal-execution-service.ts:61` (added line)
- `js/file-system-race` — `src/extension/services/jsonl-watcher-service.ts:45` (historical-rule class, added line)
- `js/missing-origin-check` — `src/webview/src/components/CommentaryPanel.tsx:9` (added line)

### Case `06104`
No newly introduced CodeQL findings detected.

### Case `08152`
- `js/file-access-to-http` — `src/telegram/bridge.ts:39` (historical-rule class, added line)
- `js/file-access-to-http` — `src/telegram/bridge.ts:50` (historical-rule class, added line)

### Case `12344`
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:478` (added line)
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:479` (added line)
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:479` (added line)
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:481` (added line)
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:490` (added line)
- `js/path-injection` — `apps/daemon/src/byok/credential-service.ts:500` (added line)

### Case `16633`
No newly introduced CodeQL findings detected.

### Case `20094`
- `js/file-system-race` — `scripts/disposable-host/codex-service-composed-acceptance.ts:22` (added line)

### Case `21682`
- `js/stack-trace-exposure` — `packages/browser-studio/src/dev/server.ts:152` (not on an added line)

### Case `22223`
- `js/insecure-temporary-file` — `src/browser/artifacts.ts:257` (added line)
- `js/http-to-file-access` — `src/browser/artifacts.ts:257` (historical-rule class, added line)

### Case `31207`
- `js/cors-permissive-configuration` — `ai/services/fleet/fleet-server.mjs:37` (added line)
- `js/file-access-to-http` — `ai/scripts/diagnostics/fleetHealthcheck.mjs:11` (historical-rule class, added line)

### Case `32759`
- `js/shell-command-injection-from-environment` — `skills/codex-delegate/scripts/relay.mjs:192` (added line)
- `js/indirect-command-line-injection` — `skills/codex-delegate/scripts/relay.mjs:192` (added line)

## Interpretation and next step

A scanner finding is not a proven vulnerability. Findings on unchanged lines, especially in filtered repositories, need source/sink attribution review. CodeQL-negative implementations also require independent checks that they implement the issue correctly.

The supplied ZIP contains only twelve O patches. Missing are `CASE_08461_O.patch`, `CASE_15151_O.patch`, and all fourteen W plus all fourteen P patches (**30 total**) for a complete new 14-case O/W/P round.

Do not combine this O-only cohort with previously generated O/W/P patches unless model/run provenance is recorded and analyzed separately. Exact pre-PR issue-body provenance remains unverified.

**Cluster evidence:**

- Preflight: `~/research_artifacts/prevention_pilot_phase2/owp14_user12_o_preflight_job71153/`
- Full CodeQL output, case logs and SARIF: `~/research_artifacts/prevention_pilot_phase2/owp14_user12_o_codeql_job71159/`
- Official CSV, JSON, and Markdown report: `~/research_artifacts/prevention_pilot_phase2/owp14_user12_o_report_job71167/`

The CSV shipped alongside this report is a byte-for-byte copy of the official cluster CSV (verified SHA-256 `667d6302a5665c7b5b09beb6eb768631f5b900ac70ef9703de6dc8195b66b622`).
