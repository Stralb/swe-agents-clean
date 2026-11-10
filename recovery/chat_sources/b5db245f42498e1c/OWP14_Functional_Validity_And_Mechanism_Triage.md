# O/W/P functional-validity and mechanism-adjudication triage

**Scope:** 40 original user-uploaded Git patches in 14 cases. This file is a manually adjudicated *triage*, not a finished all-case acceptance test. The 2 missing O patches are explicitly missing.

## Confirmed evidence

- The Wits static-analysis run found 21/O, 10/W and 15/P new CodeQL findings across the same 12 cases; those are **scanner counts, not proven vulnerabilities**.
- The offline Bun parser passes 39/40 patches. `16633_O` contains a duplicate `resolveOpenAgentsSession` declaration; `08461_W` and `08461_P` are valid when `.js` is parsed as JSX.
- `03581`: three fresh black-box watcher replications show W omits tool-result `user` records; O/W fail file-rotation delivery; P delivers both. W/P remove the selected file-race *rule*, but full end-to-end commentary remains unvalidated.
- `08152`: mocked voice-transcription checks show W/P reject `../secret` prior to network calls; O does not. P sets `redirect: error`; W relies on default redirect handling. No actual Telegram/API calls were made.
- Stand-alone helper tests passed for `31207_W` (2 tests), `16633_W` (3 tests), `06104_W` and `06104_P` (6 assertions each). They are **not original-issue acceptance tests**.
- `06104_W/P` do not implement the full bidirectional Buzz transport described by the original issue. `16633_W/P` do not establish durable authenticated FleetRun creation; `16633_O` has a syntax error. `31207_W` omits required Compose/Caddy integration.

## Case-by-case triage

| Case | Added lines O/W/P | Evidence | Open functionality/causal concern |
|---|---:|---|---|
| `00668` | 124/74/116 | Target warning persists across O/W/P; all three implement configuration migration in state.ts | Needs isolated HUD integration and migration tests; no verified prevention |
| `03429` | 61/50/101 | P removes selected warning class; filtered source and finding not on added line | Provisional source; verify provenance and actual symlink-safe revert paths |
| `03581` | 242/279/210 | W/P remove selected file-system-race warning; identical black-box watcher fixtures reveal divergent behavior | W omits tool-result user events and does not detect file replacement; P handles both; entire UI/commentary integration unvalidated |
| `06104` | 640/72/100 | All variants scanner-negative, but W/P omit Buzz relay transport/inbound-outbound wiring | W/P incomplete for full bidirectional Buzz adapter; stand-alone cursor/checkpoint tests do not validate feature |
| `08152` | 76/109/80 | Selected warning persists W/P; black-box mocks show W/P reject traversal path, O does not | Guard improvement despite scanner alert; W/P still require real voice integration tests; P explicitly rejects redirects |
| `08461` | missing/48/48 | Only W/P available; no new CodeQL warnings | Missing O implementation and feature acceptance; cannot infer prevention |
| `12344` | 72/66/108 | Filtered source; target ReDoS not reproduced by this O; substantial new path-injection findings | Cannot use this as target-warning prevention example; Windows DPAPI/credential storage runtime not validated |
| `15151` | missing/24/23 | Only W/P available; no new CodeQL warnings | Missing O implementation and UI behavior acceptance |
| `16633` | 445/55/55 | O has duplicate resolveOpenAgentsSession declaration; W/P only add policy fragments | All variants fail to demonstrate issue-level durable FleetRun integration; exclude from valid prevention denominator |
| `20094` | 140/96/75 | No historical target-warning recurrence in O; W scanner-negative | Feature acceptance unverified; lower warning count alone is not prevention |
| `21682` | 145/106/84 | Filtered source and no target warning in O; W/P scanner-negative | Test workspace package resolution against same-commit dependencies; provisional until full snapshot |
| `22223` | 258/127/92 | Selected HTTP-to-file warning persists across all three; implementations use distinct download mechanisms | Browser-authenticated sandbox downloads and CLI session artifacts need real integration; W/P infer undocumented backend endpoint behavior |
| `31207` | 223/120/164 | W removes selected warning but is filtered source and misses Compose/Caddy wiring | W fails required optional fleet-server deployment integration despite passing HTTP helper tests |
| `32759` | 21/20/42 | P scanner-negative; O/W have command-injection warnings, but selected temp-file rule absent in O | Test quoted Windows profiles, CMD special chars, read-only behavior and temporary artifact ownership on Windows |

## Prevention interpretation and next experiments

1. **Do not use raw alert reductions as the primary outcome.** Use a hierarchy: patch applies → parses/builds → fulfills the issue → selected security mechanism verified → CodeQL status. Preserve all failures and report both intent-to-treat and valid-implementation subsets.
2. **Run the fully matched acceptance fixtures** on frozen O/W/P for each issue. Audit remaining complete-source target-positive cases `00668`, `03581`, `08152`, `22223` first. The strong scanner-selected-rule disappearance is confined to `03581` in this stricter subset.
3. **For `03581`,** add independent fixtures for JSONL truncation, rotation, event filtering, lifecycle, and separate commenter session continuity; then test whole UI bridge. The existing 3-replication watcher test is important but insufficient.
4. **For `08152`,** add URL traversal, encoded slash, redirect, oversized response, voice-duration, and successful transcription tests, then verify Telegram bridge registration. A scanner warning can persist despite valid guards.
5. **For `22223`,** use recorded, authorized browser-harvest fixtures and avoid assuming nonexistent ChatGPT HTTP endpoints. Measure safe artifact saving, metadata registration, and download failure behavior.
6. **For `32759`,** use an actual Windows runtime with a space-containing profile path and a controlled fake Codex shim; also exercise CMD `%`, `!`, `^`, `&` quoting. Linux scans cannot establish correctness.
7. **Provenance:** issue-body-as-of-PR not yet established; four cases (`03429`, `12344`, `21682`, `31207`) have filtered provisional repository snapshots; modeling/run-generation comparability unverified.

## Reproducibility

- Original archives: `all_case_patches.zip` (O), `ALL_14_CASE_PATCHES.zip` (W), `ALL_CASES_PATCHES.zip` (P). All checks preserve their bytes.
- Scanner counts derive from Wits job `71212` and the archived OWP14 CodeQL comparison.
- Black-box watcher replications: `WATCHER_REPLICATION_SUMMARY.json`; voice mocks: `VOICE_BLACKBOX_RESULTS.json` in the local audit working directory.
- This triage does not claim that 40/40 projects compile or pass original-issue acceptance.
