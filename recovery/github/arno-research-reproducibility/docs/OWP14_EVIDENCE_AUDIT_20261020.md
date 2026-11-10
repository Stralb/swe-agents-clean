# October O/W/P: paired CodeQL and functional evidence intake

**Audit date:** 2026-10-20  
**Status:** source-archive integrity and archived-result consistency **verified**; new-finding differentials, original-issue functional acceptance, and intervention causality **not independently reproduced**.

## Scope and immutability

These archives were received from the researcher as read-only exports from Wits. No Wits files, Slurm jobs, working directories, or datasets were modified. They were parsed from ZIP members without archive extraction, shell execution, dependency installation, or re-running CodeQL.

| Archive | Uploaded archive SHA-256 | Manifested members independently verified |
| --- | --- | ---: |
| `03_CODEQL_SARIF_AND_SCANS.zip` | `4896827bb45257527f7816731d2b541b9dd5c8d8d00cb8755868b6083491b2cb` | **255/255** |
| `04_FUNCTIONAL_TESTS_AND_TRIAGE.zip` | `7f9b56cc69b100abf31966910b8f73d178f06ae959c420efbb3dee7dfd908392` | **226/226** |

The archives each also contain an unindexed `00_README_AND_MANIFEST/PART_INDEX.csv`; the exact set of all other members matches the index. ZIP compression and entry checksums were independently read, not merely trusted from the file name.

## Cohort and experiment identity

The recorded study covers **14 cases** and **40 arm-level patches/scans**:

| Arm | Recorded scans | Archived *new-alert* claims | Archived *new historical-rule alert* claims |
| --- | ---: | ---: | ---: |
| O (original issue) | **12** | **21** | **7** |
| W (warning-informed condition) | **14** | **10** | **4** |
| P (augmented/safety-information condition) | **14** | **15** | **5** |

Exactly **12 cases have all three arms**; case **08461** and case **15151** do not have an O patch/scan in this exported cohort. Their W and P scans are present, but they must not be included as fully paired O/W/P experiments. The recorded paired-case aggregate therefore uses 12 cases, where the W and P arms have zero new-alert counts for those two O-absent cases.

Of the 14 cases, **10 are `FULL_FROZEN_SNAPSHOT` and four `FILTERED_SOURCE_PROVISIONAL`** (03429, 12344, 21682, 31207). Within the fully three-arm-paired subset, only **eight** have full frozen snapshots; four paired cases use provisional filtered sources. This distinction is material when making baseline-comparability claims.

The corrected historical-target-recurrence index reports that the precise previously observed historical target rule was reproduced in **8/14** prior O investigations. That 8/14 is not the number of historical target alerts observed in the current 12-arm O scan: the latter is seven new historical-rule alerts, across multiple cases, and represents a different quantity.

### Recorded paired descriptive contrasts (not effect estimates)

From the archived 12-case comparison: W has fewer total reported new CodeQL alerts than O in **7/12 cases** and the same number in **5/12**; P has fewer in **4/12** and the same in **8/12**. No paired case in this table has a higher reported new-alert count in W or P. On the historical target rule, the archived table reports no new target alerts in W where O had target alerts in cases **03581** and **31207**, and no new target alerts in P where O had target alerts in **03429** and **03581**. Two of those case-level contrasts rely on filtered provisional source snapshots.

These are observations within already-generated patches and should **not** be described as randomized treatment effects, proven prevention, or minimum sufficient safety-information experiments.

## Independent checks performed

1. Validated the recorded SHA-256 checksum and byte length of every indexed ZIP member: **481/481** passing across both uploads.
2. Independently parsed each of the **40 after-scan SARIF files** and confirmed that the number of results equals each corresponding `RESULT.json` `codeql_after_total`.
3. Checked that every archived scanner command exit code was zero, each case has the expected CodeQL **2.25.6** version, and all 40 records report `SCAN_COMPLETE`.
4. Matched per-case `RESULT.json` new/target counts and target-on-added-line counts against `OWP14_SUMMARY.json`; checked the separate 14-row comparison CSV against the JSON summary.
5. Confirmed that every alert listed as `new_strong_alerts` in the case record has a matching **rule ID, file URI and location line in the after-scan SARIF**. This proves after-scan presence, not newness relative to baseline.
6. Matched all **40 scanner-side patch SHA-256 values** to the corresponding syntax-check records.
7. Verified that all 14 case-intake packets claim their source repository content agrees with the frozen input and that all 40 exported patches are recorded as applied; this is a cross-check of **reported** status, not an independent reconstruction from repository archive bytes.
8. Verified every arm in a case reports the **same baseline SARIF SHA-256**. However, the `frozen_source_sha256` values differ across arms in **all 14 cases**. It may reflect differently packaged source archives; source-tree content equivalence must still be checked against original repository snapshots. We do not assert that bases differed in contents.

### Critical independent-verification limit

The ZIP exports include **40 after-scan SARIF files but no baseline/before SARIF files**. Thus, despite the internal consistency checks above, the archived `new_strong_total`, `new_conservative_total`, and historical-target `new` classifications **cannot be independently regenerated from the supplied SARIF alone**. The hashes of the missing baseline SARIF files are recorded and can be used to verify a later export.

## Functional evidence: 40 patch-level syntax checks, not 40 successful implementations

The initial Bun 1.4.2 parser check records **37/40 syntax passes**. The two 08461 W/P failures were `Unexpected <` for a JSX-containing `.js` file, with the same parser failure already present in the baseline. A JSX-aware recheck records **39/40 passes**, leaving **16633-O** as a confirmed patch-level syntax failure: duplicate declaration of `resolveOpenAgentsSession` in `apps/sarah/src/server.ts`. The case's CodeQL result nevertheless has **zero recorded new warnings**.

These syntax checks cover selected changed JS/TS/JSX files and are not equivalent to a full build, package installation, end-to-end test, behavioural equivalence, or acceptance of the issue's original requirements.

Four additional **standalone subcomponent checks** passed (06104 W and P; 16633 W; 31207 W). They are explicitly designated `SUBCOMPONENT_ONLY_NOT_FULL_FUNCTIONAL_ACCEPTANCE`, and no archive record elevates them to full project-level acceptance. The isolated environment inventory for job 71359 reported no `node`, `npm`, `pnpm`, `bun`, `tsc`, `vitest`, `jest`, or Docker available in **that environment**; this does not assert those tools were unavailable on all Wits nodes or at all later times.

The two separate pilot-3 functional-result strata present in the export are **historical independent experiments**, not part of the 40-patch O/W/P syntax denominator. They must not be pooled with O/W/P acceptance results.

## Scientific interpretation and blockers

The top-level scanner comparison explicitly labels itself `exploratory scanner comparison only` and marks all three of the following as **false**:

- `issue_asof_PR_provenance_verified`
- `functional_acceptance_verified`
- `agent_generation_cohort_comparability_verified`

This prohibits a conclusion that warning-informed additions causally eliminate vulnerabilities, that interventions produce functionally equivalent implementations, or that a practical deployment could know a historical warning in advance. CodeQL alert differences are scanner observations; warning hindsight remains a retrospective oracle, not a deployable predictor.

**Before a confirmatory result:** recover all 14 per-case baseline SARIF files (check against the recorded SHA-256 values), identify the exact generator prompts/traces and source snapshot identities, prove as-of-PR issue provenance, demonstrate same-base content equivalence, and define/run original-issue acceptance tests on deliberately isolated writable copies. Preserve functional failures and newly introduced *non-target* warnings rather than reporting only disappearance of the selected target.

## Committed artifacts and reproducibility

- `tools/owp14_archive_audit.py`: Python-standard-library checker, reads input ZIP files, does not extract or mutate them, and prints a self-contained JSON audit.
- `tests/test_owp14_archive_audit.py`: synthetic fixtures for index completeness, SHA-256 detection, ambiguous member names and SARIF parsing. No private cases or scanner execution needed.
- `provenance/owp14_intake_verified_20261020.json`: audit output from the exact uploaded ZIPs.
- `provenance/owp14_case_arm_counts_20261020.csv`: compact, case-ID-only, source-labelled, per-arm recorded counts. **Counts labelled `new_claimed` are not independently recomputed deltas.**

To rerun the intake audit on a **local** machine holding the ZIPs:

```bash
python -m tools.owp14_archive_audit /path/to/03_CODEQL_SARIF_AND_SCANS.zip /path/to/04_FUNCTIONAL_TESTS_AND_TRIAGE.zip
python -m unittest discover -s tests -v
```

**No raw SARIF, security alert text, original issue bodies, private source snapshots, or historical repository patches were committed.**
