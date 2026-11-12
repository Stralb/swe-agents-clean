# 22 October 2026 — live Wits C1/C2 crosswalk and C6 scalar replay

**Status:** `PASS_C1_C2_ORIGINAL_ROW_CROSSWALK_AND_CANDIDATE_DB_SCALAR_ARITHMETIC`. This is not complete C6 original-source replication or evidence that scanner-positive labels represent actual vulnerabilities.

## Access and provenance

Read-only Wits DCR cluster connector, authenticated as `astrauss`, research root `/home-mscluster/astrauss/research_artifacts`. No cluster files, jobs, scanner configurations or third-party repositories were changed.

Original research artifacts, read in chunks without saving private case-level rows to this Git repository:

- `matched_control_c1_v1_1/C1_CASE_SCANNER_OPPORTUNITY_3809.csv` — 841,710 bytes. Previously independently attested SHA-256 `6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b`.
- `matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv` — 56,175 bytes. Previously independently attested SHA-256 `4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b`.
- `c6_context_completion_v1_0/C6_CONTROL_CONTEXT_190.csv` and its context/QC JSON.
- `miner.agentic-js.eval.20260720_224159.full3809-continuation.db` — *later continuation SQLite*, **not** the independently SHA-authenticated final 29 August frozen SQLite.

The original C1 full byte digest and C2 full byte digest were verified in earlier recorded recovery passes, **not recomputed from these particular Wits read chunks**. The live chunk streams were checked for expected size, order, parsable rows and identical C1/C2 fields. Claims below are conditional on those exact source identities and on the separately identified continuation SQLite snapshot where used.

## Full original C1↔C2 case-level agreement

An independent, read-only streaming comparison covered the entire 841,710-byte C1 table across four non-overlapping byte ranges, with overlapping chunk reads only at segment boundaries. The C2 CSV was reread in full for each segment. Each C1 row was assigned to exactly one byte segment based on its original line-start position.

| C1 original-byte segment | Rows | Stored positive | Matched case records checked | Field mismatches |
| --- | ---: | ---: | ---: | ---: |
| [0, 280000) | 1,279 | 41 | 100 | 0 |
| [280000, 560000) | 1,270 | 64 | 128 | 0 |
| [560000, 700000) | 627 | 40 | 71 | 0 |
| [700000, 841710) | 633 | 47 | 81 | 0 |
| **Total** | **3,809** | **192** | **380** | **0** |

The 380 matched source records are 190 scanner-positive cases plus 190 C2 control cases, with neither repeated matched positives nor repeated controls. Every selected C1 record matched C2 for **case positivity, repository, PR creation timestamp, scanner opportunity signature, changed-line count and changed-file count**. Thus the preserved C1→C2 case-level membership and copied matching covariates reconcile, not just the two JSON summary manifests.

A separate complete 190-row C2 metadata audit found:
- **115** Tier-A same-repository pairs, **75** Tier-B cross-repository pairs.
- **181** exactly matching opportunity signatures; **9** allowed scanner-opportunity supersets.
- All tier, signature-set relations, uniqueness and positive/control disjointness checks passed.
- Maximum absolute PR-time matching separation **61.796273 days**, below the 90-day archived caliper.
- Largest archived +1-smoothed changed-line ratio **3.984331**, largest changed-file ratio **3.857143**, both below the approximately fourfold archived caliper.
- **Zero** C2 matching-rule or copied-field inconsistencies.

This **closes the C1↔C2 original-row accounting crosswalk**, but not the correctness of 192 positive vulnerability labels, regeneration from the exact frozen final SQLite, or the original matching optimizer's global optimality.

## C6: two more nine-family primary comparisons independently reconstructed

For all 190 C2 matched pairs, case IDs were joined read-only to the **later continuation SQLite** issue and PR authors/timestamps. The frozen C6 control context CSV was separately inspected. The derived statistics match the historic C6 report; they are candidate-DB checks, not fully authenticated final-database or original C6 CSV byte replays.

**Same issue/PR author:** a case-insensitive comparison produced the paired 2×2 table: positive-only **30**, control-only **29**, both **39**, neither **92** (N=190). Thus 69/190 positive vs 68/190 control; exact two-sided McNemar/binomial p=**1.000**, matching historical p=1.000. In the 115 Tier-A same-repo pairs, there were 46 positive and 45 control same-author cases, without a claimed subgroup significance test.

**Issue-to-PR creation delay:** for each match, duration is `PR.created_at - issue.created_at` in hours. Positive median **12.456667 h**, control median **16.170278 h**. The within-pair positive-minus-control differences give Wilcoxon positive rank sum **8,183**, negative rank sum **9,962**, n=190, no tied absolute differences; two-sided asymptotic normal p≈**0.241232** without continuity correction. This reproduces C6's historical rounded p=0.241. The median paired difference is approximately **−0.405 h**; it is not the difference between the two marginal medians.

Together with the five already reported indexed paired-contingency Stuart–Maxwell checks, **seven of nine** primary comparisons have independent computational checks, but their provenance levels are **not equal**. The five remain indexed-aggregate only; these two use actual case-level pair IDs with a nonfinal candidate SQLite snapshot.

## Temporal-order sensitivity (exploratory, not historical C6)

Among the 190 matched pairs, **nine pairs** have at least one issue created *after* the corresponding PR: four positive-case inversions and six control-case inversions (one pair has both). These inversions are genuine issue/PR creation-order observations in the candidate SQLite. They require retrospective-linkage/issue-edit chronology assessment before describing the issue as a cause of implementation.

Dropping all nine affected pairs leaves **181 pairs**. The same paired Wilcoxon calculation then gives W+=**7,252**, z≈**−1.393323**, two-sided p≈**0.163522** (no continuity correction). Neither the full-cohort nor restricted delay association is significant at alpha=0.05. This is exploratory exclusion sensitivity; original cohort membership and frozen historical results remain unchanged. No updated specificity or goal-alignment significance is inferred from this delay-only sensitivity.

## C6 context missingness and source limitations

The original `C6_CONTEXT_QC.json` records 190 unique controls, **569** review-audit rows, **one** missing account age, **one** missing author association, and **three** missing prior-repository-activity values. The `C6_CONTROL_CONTEXT_190.csv` has 47 recorded `Yes` and 143 recorded `No` controls for human review. On one control, the original review API returned HTTP 404 and the context extractor defaulted the missing review list to `[]` and wrote **`No`**. That is **unknown, not an observed zero-review finding** unless independently resolved.

The historical C6 human-review comparison reports 189 complete pairs, but this observation alone does **not** prove that the failed control lookup is the one excluded. The prior-repository-activity comparison reports p=0.336 over 190 pairs although three controls have missing raw historical-search values; exactly how the historical C6 master handles these cells has not been verified.

**Two primary tests remain outstanding:** human review (historical p=0.419, n=189) and any prior repository activity (historical p=0.336, n=190). The original pair-level C6 master and its hash-verified bytes are needed to reproduce their treatment of missingness and statistics. Do not treat GitHub API HTTP 404/422 failures as proof of non-activity.

## Remaining scientific release gates

1. Obtain and authenticate the original final 29 August SQLite (`126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`), then repeat the case-level author/timing tests against **that** source.
2. Obtain separately approved, SHA-attested C4/C5/C6 original pair-level coding and context outputs; redo all nine tests and the 115 same-repository sensitivity, including repository-blocked resampling.
3. Inspect the nine chronological-inversion pairs and issue-edit timestamps without silently dropping records.
4. Resolve the separate 43 D-versus-D7 semantic-label disputes through source evidence (42 tier changes; one route change). Do not infer the correct labels from the later export alone.
5. Recover all 14 historical before-SARIF CodeQL baselines to independently re-establish introduced warnings and retrospective intervention outcomes.
6. Verify the historical tool/QL-pack versions, issue acceptance/functional correctness and any proposed causal or prospective claim.

No private issue/PR text, case IDs, repository identifiers, or full original CSV/SQLite bytes are stored in this document or Git. This audit changes no historical source labels.
