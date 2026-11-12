# Seven-case new CodeQL evaluation, 2026-10-20

CodeQL 2.25.6, JavaScript security-extended. Seven unique patches, because P1/P2/P3 were byte-identical within each case. Functionality is NOT verified. No minimum safety text can be concluded.

| Case | Before | After | New (fingerprint) | New (conservative) | Scanner-negative |
|---|---:|---:|---:|---:|---|
| 03429 | 42 | 40 | 1 | 1 | False |
| 03581 | 82 | 82 | 0 | 0 | True |
| 08152 | 4 | 6 | 2 | 2 | False |
| 12344 | 758 | 764 | 7 | 6 | False |
| 22223 | 41 | 41 | 0 | 0 | True |
| 31207 | 60 | 62 | 2 | 2 | False |
| 32759 | 12 | 12 | 0 | 0 | True |

The 12344 discrepancy (7 fingerprint vs 6 conservative) is preserved as an unresolved identity/granularity disagreement; no automatic normalization is assumed. Inspect both before/after SARIF.

## Finding detail

- 03429: js/insecure-temporary-file, src/core/FileSystemUtils.ts:334 — Insecure creation of file in [the os temp dir](1).
- 08152: js/incomplete-url-substring-sanitization, src/telegram/voice.test.ts:17 — '[api.telegram.org](1)' can be anywhere in the URL, and arbitrary hosts may come before or after it.
- 08152: js/file-access-to-http, src/telegram/voice.ts:55 — Outbound network request depends on [file data](1).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:497 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:499 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:499 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:501 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:512 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
This path depends on a [user-provided value](3).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:536 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
- 12344: js/path-injection, apps/daemon/src/byok/credential-service.ts:548 — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
This path depends on a [user-provided value](3).
- 31207: js/cors-permissive-configuration, ai/services/fleet/composedFleetServer.mjs:36 — CORS Origin allows broad access due to [permissive or user controlled value](1).
- 31207: js/file-access-to-http, ai/scripts/diagnostics/fleetHealthcheck.mjs:25 — Outbound network request depends on [file data](1).

Zero new CodeQL findings does not prove security or functional completeness.
