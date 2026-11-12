# Third-iteration O-only CodeQL screen: 65 cases

CodeQL 2.25.6, JavaScript security-extended. Archived frozen prepatch SARIF as baseline.
**Do not treat alert counts as confirmed vulnerabilities or O/W/P treatment effects.**

Cases scanned: 65/65.
Newly scanner-positive cases outside existing 14: 5/51.
Full-snapshot positives outside existing 14: 4.
Strongest new target-class on-added-line candidates: [].

| Case | Cohort | Source | Apply/scan | New strong | New conservative | Historical-class | Added-line historical | Tier |
|---|---|---|---|---:|---:|---:|---:|---|
| 00299 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 00461 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 00608 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 00648 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 00653 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 00668 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 1 | 1 | 1 | ALREADY_IN_14_REPLICATION |
| 03429 | already 14 | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 1 | 1 | 1 | 0 | ALREADY_IN_14_REPLICATION |
| 03490 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 03581 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 2 | 2 | 2 | 2 | ALREADY_IN_14_REPLICATION |
| 03582 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 03684 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 03882 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 04134 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 2 | 2 | 0 | 0 | C_NEW_RULE_ON_ADDED_LINE_FULL |
| 04135 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 04379 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 2 | 1 | 0 | 0 | C_NEW_RULE_ON_ADDED_LINE_FULL |
| 04811 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 05264 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 05267 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 05355 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 06104 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 3 | 3 | 3 | 0 | ALREADY_IN_14_REPLICATION |
| 06145 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 06150 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 2 | 2 | 2 | 2 | E_FILTERED_SOURCE_PROVISIONAL |
| 07682 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 07930 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 08149 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 08152 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 1 | 1 | 1 | ALREADY_IN_14_REPLICATION |
| 08461 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 09998 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 10155 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 10326 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 10339 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 1 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 10361 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 12344 | already 14 | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 6 | 5 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 12898 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 14194 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 15151 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 15739 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 15748 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16209 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 0 | 0 | 0 | C_NEW_RULE_ON_ADDED_LINE_FULL |
| 16213 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 0 | 0 | 0 | D_NEW_RULE_OTHER_LOCATION_FULL |
| 16262 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 1 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16343 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16392 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16394 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16482 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16534 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 16633 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 16776 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 17048 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 17075 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 17320 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 17428 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 17660 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 18465 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 18473 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 20086 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 20094 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 1 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 21651 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 21654 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 21682 | already 14 | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 22223 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 2 | 2 | 0 | 0 | ALREADY_IN_14_REPLICATION |
| 25473 | new | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 28354 | new | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 0 | 0 | 0 | 0 | NO_NEW_SCANNER_FINDING |
| 31207 | already 14 | FILTERED_SOURCE_PROVISIONAL | SCAN_COMPLETE | 1 | 1 | 1 | 1 | ALREADY_IN_14_REPLICATION |
| 32759 | already 14 | FULL_FROZEN_SNAPSHOT | SCAN_COMPLETE | 1 | 1 | 0 | 0 | ALREADY_IN_14_REPLICATION |

## New cohort candidates and scanner traces

### 04134 — C_NEW_RULE_ON_ADDED_LINE_FULL
- js/file-system-race at v3/@claude-flow/cli/src/init/executor.ts:992 [added line] — The file may have changed since it [was checked](1).
- js/file-system-race at v3/@claude-flow/cli/src/init/executor.ts:994 [added line] — The file may have changed since it [was checked](1).

### 04379 — C_NEW_RULE_ON_ADDED_LINE_FULL
- js/path-injection at packages/server/src/services/hermes/channel-proxy.ts:44 [added line] — This path depends on a [user-provided value](1).
This path depends on a [user-provided value](2).
This path depends on a [user-provided value](3).
- js/remote-property-injection at packages/server/src/controllers/hermes/config.ts:269 [added line] — A property name to write to depends on a [user-provided value](1).

### 06150 — E_FILTERED_SOURCE_PROVISIONAL
- js/file-system-race at ai/daemons/wake/shapeBHostMain.mjs:17 [added line] [historical class] — The file may have changed since it [was checked](1).
- js/file-system-race at ai/daemons/wake/shapeBHostReceiver.test.mjs:81 [added line] [historical class] — The file may have changed since it [was checked](1).

### 16209 — C_NEW_RULE_ON_ADDED_LINE_FULL
- js/missing-rate-limiting at src/server.ts:421 [added line] — This route handler performs [a file system access](1), but is not rate-limited.

### 16213 — D_NEW_RULE_OTHER_LOCATION_FULL
- js/missing-rate-limiting at src/server.ts:151 [not added line] — This route handler performs [a file system access](1), but is not rate-limited.

## Eligibility rules
- Prioritize full snapshots and historical class recurrence, with source-to-sink review.
- New warnings in unrelated rule classes are exploratory only.
- Never automatically add provisional filtered sources based only on scanner findings.
- A patch that fails to apply or has no new findings does not count as a positive.
