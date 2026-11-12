# O-only CodeQL evaluation: 12 uploaded patches

These are exploratory scan results, not an O/W/P treatment comparison.
Missing O cases: 8461, 15151. Uploaded W and P patches: none.
All twelve O patches applied to the frozen repository copies.
CodeQL suite: codeql/javascript-queries:codeql-suites/javascript-security-extended.qls. CodeQL version: 2.25.6.
Historical exact issue-body versions: unverified. Filtered base cases are provisional.
Functional correctness: NOT VALIDATED; scanner-negative does not imply correctness.

| Case | Source | Scanner | Before | After | New alerts | New historical-target alerts | On added lines |
|---|---|---|---:|---:|---:|---:|---:|
| 00668 | full | SCAN_COMPLETE | 128 | 129 | 1 | 1 | 1 |
| 03429 | filtered | SCAN_COMPLETE | 42 | 40 | 1 | 1 | 0 |
| 03581 | full | SCAN_COMPLETE | 82 | 85 | 3 | 1 | 3 |
| 06104 | full | SCAN_COMPLETE | 271 | 271 | 0 | 0 | 0 |
| 08152 | full | SCAN_COMPLETE | 4 | 6 | 2 | 2 | 2 |
| 12344 | filtered | SCAN_COMPLETE | 758 | 763 | 6 | 0 | 6 |
| 16633 | full | SCAN_COMPLETE | 213 | 213 | 0 | 0 | 0 |
| 20094 | full | SCAN_COMPLETE | 158 | 159 | 1 | 0 | 1 |
| 21682 | filtered | SCAN_COMPLETE | 151 | 152 | 1 | 0 | 0 |
| 22223 | full | SCAN_COMPLETE | 41 | 43 | 2 | 1 | 2 |
| 31207 | filtered | SCAN_COMPLETE | 60 | 62 | 2 | 1 | 2 |
| 32759 | full | SCAN_COMPLETE | 12 | 14 | 2 | 0 | 2 |

## New scanner alerts, by case

### Case 00668: SCAN_COMPLETE
- js/file-system-race at src/hud/state.ts:198 [on added line] [historical target class] — The file may have changed since it [was checked](1).

### Case 03429: SCAN_COMPLETE
- js/insecure-temporary-file at src/core/FileSystemUtils.ts:301 [not on added line] [historical target class] — Insecure creation of file in [the os temp dir](1).

### Case 03581: SCAN_COMPLETE
- js/incomplete-sanitization at src/extension/services/terminal-execution-service.ts:61 [on added line] — This does not escape backslash characters in the input.
- js/file-system-race at src/extension/services/jsonl-watcher-service.ts:45 [on added line] [historical target class] — The file may have changed since it [was checked](1).
- js/missing-origin-check at src/webview/src/components/CommentaryPanel.tsx:9 [on added line] — Postmessage handler has no origin check.

### Case 06104: SCAN_COMPLETE
No strong-new CodeQL alerts.

### Case 08152: SCAN_COMPLETE
- js/file-access-to-http at src/telegram/bridge.ts:39 [on added line] [historical target class] — Outbound network request depends on [file data](1).
- js/file-access-to-http at src/telegram/bridge.ts:50 [on added line] [historical target class] — Outbound network request depends on [file data](1).

### Case 12344: SCAN_COMPLETE
- js/path-injection at apps/daemon/src/byok/credential-service.ts:478 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- js/path-injection at apps/daemon/src/byok/credential-service.ts:479 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- js/path-injection at apps/daemon/src/byok/credential-service.ts:479 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- js/path-injection at apps/daemon/src/byok/credential-service.ts:481 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- js/path-injection at apps/daemon/src/byok/credential-service.ts:490 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2). This path depends on a [user-provided value](3).
- js/path-injection at apps/daemon/src/byok/credential-service.ts:500 [on added line] — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).

### Case 16633: SCAN_COMPLETE
No strong-new CodeQL alerts.

### Case 20094: SCAN_COMPLETE
- js/file-system-race at scripts/disposable-host/codex-service-composed-acceptance.ts:22 [on added line] — The file may have changed since it [was checked](1).

### Case 21682: SCAN_COMPLETE
- js/stack-trace-exposure at packages/browser-studio/src/dev/server.ts:152 [not on added line] — This information exposed to the user depends on [stack trace information](1).

### Case 22223: SCAN_COMPLETE
- js/insecure-temporary-file at src/browser/artifacts.ts:257 [on added line] — Insecure creation of file in [the os temp dir](1).
- js/http-to-file-access at src/browser/artifacts.ts:257 [on added line] [historical target class] — Write to file system depends on [Untrusted data](1).

### Case 31207: SCAN_COMPLETE
- js/cors-permissive-configuration at ai/services/fleet/fleet-server.mjs:37 [on added line] — CORS Origin allows broad access due to [permissive or user controlled value](1).
- js/file-access-to-http at ai/scripts/diagnostics/fleetHealthcheck.mjs:11 [on added line] [historical target class] — Outbound network request depends on [file data](1).

### Case 32759: SCAN_COMPLETE
- js/shell-command-injection-from-environment at skills/codex-delegate/scripts/relay.mjs:192 [on added line] — This shell command depends on an uncontrolled [absolute path](1). This shell command depends on an uncontrolled [absolute path](2). This shell command depends on an uncontrolled [a
- js/indirect-command-line-injection at skills/codex-delegate/scripts/relay.mjs:192 [on added line] — This command depends on an unsanitized [command-line argument](1).

## Caveats
- New scanner findings require source-to-sink manual adjudication; a rule ID alone is not a confirmed exploit.
- Four cases have provisional filtered source snapshots.
- Models, prompts and generation contexts for historical O attempts must remain separately labelled.
- No claim of vulnerability prevention is possible without paired W and P patches and functionality verification.
