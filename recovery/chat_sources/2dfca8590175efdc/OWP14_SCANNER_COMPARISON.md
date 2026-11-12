# O/W/P static-analysis comparison — 14 cases

IMPORTANT: This is a descriptive CodeQL comparison, not proof of vulnerability prevention.
The historical W warning is a retrospective oracle intervention, not a deployable new-task workflow.
Original issue version at historical pre-PR time is not verified.
Functional correctness has not been independently validated; an incomplete patch may have fewer warnings.
Models, random seeds and generation sessions were not proven homogeneous.
Four filtered source snapshots remain provisional; two O patches were not uploaded.
CodeQL 2.25.6; javascript-security-extended suite; source CodeQL SARIF baseline hashes checked.

## Summary statistics

- three arm paired cases: 12
- O scans: 12
- W scans: 14
- P scans: 14
- missing O: [8461, 15151]
- filtered provisional: [3429, 12344, 21682, 31207]
- historical target previously reproduced count: 8
- total alerts paired: {'O': 21, 'W': 10, 'P': 15}
- target alerts paired: {'O': 7, 'W': 4, 'P': 5}
- W fewer total cases: 7
- W same total cases: 5
- W more total cases: 0
- P fewer total cases: 4
- P same total cases: 8
- P more total cases: 0
- W no target given O target: [3581, 31207]
- P no target given O target: [3429, 3581]

## Results by case
| Case | Source | O new | W new | P new | O target | W target | P target | Same baseline |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 00668 | full | 1 | 1 | 1 | 1 | 1 | 1 | True |
| 03429 | filtered | 1 | 1 | 0 | 1 | 1 | 0 | True |
| 03581 | full | 3 | 1 | 1 | 1 | 0 | 0 | True |
| 06104 | full | 0 | 0 | 0 | 0 | 0 | 0 | True |
| 08152 | full | 2 | 1 | 2 | 2 | 1 | 2 | True |
| 08461 | full | N/A | 0 | 0 | N/A | 0 | 0 | True |
| 12344 | filtered | 6 | 3 | 6 | 0 | 0 | 0 | True |
| 15151 | full | N/A | 0 | 0 | N/A | 0 | 0 | True |
| 16633 | full | 0 | 0 | 0 | 0 | 0 | 0 | True |
| 20094 | full | 1 | 0 | 1 | 0 | 0 | 0 | True |
| 21682 | filtered | 1 | 0 | 0 | 0 | 0 | 0 | True |
| 22223 | full | 2 | 1 | 2 | 1 | 1 | 1 | True |
| 31207 | filtered | 2 | 0 | 2 | 1 | 0 | 1 | True |
| 32759 | full | 2 | 2 | 0 | 0 | 0 | 0 | True |

## Full new scanner findings per arm

### Case 00668
- O: js/file-system-race at src/hud/state.ts:198 (added line) (selected warning class) — The file may have changed since it [was checked](1).
- W: js/file-system-race at src/hud/state.ts:196 (added line) (selected warning class) — The file may have changed since it [was checked](1).
- P: js/file-system-race at src/hud/state.ts:183 (added line) (selected warning class) — The file may have changed since it [was checked](1).

### Case 03429
- O: js/insecure-temporary-file at src/core/FileSystemUtils.ts:301 (not added line) (selected warning class) — Insecure creation of file in [the os temp dir](1).
- W: js/insecure-temporary-file at src/core/FileSystemUtils.ts:301 (not added line) (selected warning class) — Insecure creation of file in [the os temp dir](1).
- P: no new scanner findings

### Case 03581
- O: js/incomplete-sanitization at src/extension/services/terminal-execution-service.ts:61 (added line) — This does not escape backslash characters in the input.
- O: js/file-system-race at src/extension/services/jsonl-watcher-service.ts:45 (added line) (selected warning class) — The file may have changed since it [was checked](1).
- O: js/missing-origin-check at src/webview/src/components/CommentaryPanel.tsx:9 (added line) — Postmessage handler has no origin check.
- W: js/missing-origin-check at src/webview/src/components/CommentaryPanel.tsx:9 (added line) — Postmessage handler has no origin check.
- P: js/missing-origin-check at src/webview/src/components/CommentaryPanel.tsx:6 (added line) — Postmessage handler has no origin check.

### Case 06104
- O: no new scanner findings
- W: no new scanner findings
- P: no new scanner findings

### Case 08152
- O: js/file-access-to-http at src/telegram/bridge.ts:39 (added line) (selected warning class) — Outbound network request depends on [file data](1).
- O: js/file-access-to-http at src/telegram/bridge.ts:50 (added line) (selected warning class) — Outbound network request depends on [file data](1).
- W: js/file-access-to-http at src/telegram/voice.ts:28 (added line) (selected warning class) — Outbound network request depends on [file data](1).
- P: js/file-access-to-http at src/telegram/voice.ts:24 (added line) (selected warning class) — Outbound network request depends on [file data](1).
- P: js/file-access-to-http at src/telegram/voice.ts:36 (added line) (selected warning class) — Outbound network request depends on [file data](1).

### Case 08461
- O: not uploaded
- W: no new scanner findings
- P: no new scanner findings

### Case 12344
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:478 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:479 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:479 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:481 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:490 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2). This path depends on a [user-provided value](3).
- O: js/path-injection at apps/daemon/src/byok/credential-service.ts:500 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- W: js/path-injection at apps/daemon/src/byok/credential-service.ts:486 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- W: js/path-injection at apps/daemon/src/byok/credential-service.ts:496 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2). This path depends on a [user-provided value](3).
- W: js/path-injection at apps/daemon/src/byok/credential-service.ts:509 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:472 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:473 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:473 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:475 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:485 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2). This path depends on a [user-provided value](3).
- P: js/path-injection at apps/daemon/src/byok/credential-service.ts:500 (added line) — This path depends on a [user-provided value](1). This path depends on a [user-provided value](2).

### Case 15151
- O: not uploaded
- W: no new scanner findings
- P: no new scanner findings

### Case 16633
- O: no new scanner findings
- W: no new scanner findings
- P: no new scanner findings

### Case 20094
- O: js/file-system-race at scripts/disposable-host/codex-service-composed-acceptance.ts:22 (added line) — The file may have changed since it [was checked](1).
- W: no new scanner findings
- P: js/file-system-race at scripts/disposable-host/codex-service-composed-acceptance.ts:25 (added line) — The file may have changed since it [was checked](1).

### Case 21682
- O: js/stack-trace-exposure at packages/browser-studio/src/dev/server.ts:152 (not added line) — This information exposed to the user depends on [stack trace information](1).
- W: no new scanner findings
- P: no new scanner findings

### Case 22223
- O: js/insecure-temporary-file at src/browser/artifacts.ts:257 (added line) — Insecure creation of file in [the os temp dir](1).
- O: js/http-to-file-access at src/browser/artifacts.ts:257 (added line) (selected warning class) — Write to file system depends on [Untrusted data](1).
- W: js/http-to-file-access at src/browser/chatgptFiles.ts:81 (added line) (selected warning class) — Write to file system depends on [Untrusted data](1).
- P: js/insecure-temporary-file at src/browser/chatgptFiles.ts:63 (added line) — Insecure creation of file in [the os temp dir](1).
- P: js/http-to-file-access at src/browser/chatgptFiles.ts:63 (added line) (selected warning class) — Write to file system depends on [Untrusted data](1).

### Case 31207
- O: js/cors-permissive-configuration at ai/services/fleet/fleet-server.mjs:37 (added line) — CORS Origin allows broad access due to [permissive or user controlled value](1).
- O: js/file-access-to-http at ai/scripts/diagnostics/fleetHealthcheck.mjs:11 (added line) (selected warning class) — Outbound network request depends on [file data](1).
- W: no new scanner findings
- P: js/cors-permissive-configuration at ai/services/fleet/composedFleetServer.mjs:25 (added line) — CORS Origin allows broad access due to [permissive or user controlled value](1).
- P: js/file-access-to-http at ai/scripts/diagnostics/fleetHealthcheck.mjs:7 (added line) (selected warning class) — Outbound network request depends on [file data](1).

### Case 32759
- O: js/shell-command-injection-from-environment at skills/codex-delegate/scripts/relay.mjs:192 (added line) — This shell command depends on an uncontrolled [absolute path](1). This shell command depends on an uncontrolled [absolute path](2). This shell command depends on an uncontrolled [a
- O: js/indirect-command-line-injection at skills/codex-delegate/scripts/relay.mjs:192 (added line) — This command depends on an unsanitized [command-line argument](1).
- W: js/shell-command-injection-from-environment at skills/codex-delegate/scripts/relay.mjs:262 (added line) — This shell command depends on an uncontrolled [absolute path](1). This shell command depends on an uncontrolled [absolute path](2). This shell command depends on an uncontrolled [a
- W: js/indirect-command-line-injection at skills/codex-delegate/scripts/relay.mjs:262 (added line) — This command depends on an unsanitized [command-line argument](1).
- P: no new scanner findings

## Interpretation caveats
- Differences in warnings are not automatically caused by the intervention; functional tests and mechanism adjudication are necessary.
- A CodeQL rule-name match does not imply identical source and sink or proven exploitation.
- Original-issue-only O patches come from a separate historical generation cohort unless generation settings are confirmed.
- Scanner-negative implementations may be functionally incomplete.
- Missing O outcomes and filtered snapshots are explicitly represented, not imputed.
