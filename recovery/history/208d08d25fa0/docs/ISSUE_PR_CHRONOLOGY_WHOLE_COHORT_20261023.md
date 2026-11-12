# Full-cohort linked-issue chronology: original C1 and C2 crosswalk

**Checkpoint:** 23 October 2026, South Africa local time.  
**Scope:** recorded chronology from a *later continuation SQLite* cross-referenced to the full original C1 cohort and C2 matching. Neither the final frozen SQLite nor historical issue-body snapshots are authenticated here.

[Case-ID-only provenance ledger](../provenance/c1_c2_late_issue_chronology_census_20261023.json) · [Read-only verifier](../analysis/c1_c2_late_issue_chronology_gate.py) · [Four positive-workflow deep dive](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md)

## Methods and denominators

Read-only Wits queries joined cases to issues and pull requests through their foreign keys and compared the UTC issue creation time with PR creation and PR merge times. Disjoint case-ID ranges covered the 3,809-case later continuation database. An independent query returned all 49 case IDs with issue creation strictly after PR creation.

The full 841,710-byte original C1 source was scanned in two disjoint source-record-start-byte segments: 3,809 rows, 192 scanner-positive and 3,617 scanner-negative. The full 56,175-byte original C2 matched-pair CSV was separately read: 190 original positive-control pairs, 115 Tier A and 75 Tier B. All 49 late-issue candidate IDs were cross-checked against the original C1 positivity column and all 190 C2 pair IDs.

The original C1 and C2 complete-file SHA-256 hashes were independently attested in **earlier** recovery work and are pinned in the new ledger. The exact full-file SHA values were **not recomputed in this particular analysis run**. The new checker can later SHA-authenticate approved local original C1/C2 byte copies, outside Git. C1/C2 source identity does not authenticate timestamp correctness in the different continuation SQLite.

## Whole-cohort findings

| C1 cohort | Linked issue created after PR opened | Cohort denominator | Percentage |
| --- | ---: | ---: | ---: |
| Scanner-positive | 4 | 192 | 2.08% |
| Scanner-negative | 45 | 3,617 | 1.24% |
| **All** | **49** | **3,809** | **1.29%** |

**Five of the 49 issues were created after the PR had already merged**, and every one is a scanner-negative C1 case. The five affected case IDs (stored in the private ledger) are 11280, 16358, 16603, 37310 and 44072. Their linked issues cannot have supplied instructions to those completed PRs, although separate earlier communications are unknown.

A post-PR-opening issue may still inform subsequent commits: the meaningful exposure time is the **specific root-producing implementation commit**, not necessarily the PR creation date. Current GitHub issue descriptions are not necessarily exact historical as-of-commit text.

## Frozen matched C2 pairing affected by chronology

Nine of 190 pairs have a late-created linked issue on either side, comprising:
- four pairs with a late issue on the scanner-positive side;
- six with a late issue on the control side;
- **one pair on both sides**, giving nine unique affected pairs;
- four Tier-A pairs and five Tier-B pairs.

This reconciles the earlier nine-pair issue-to-PR-delay exploratory exclusion (190→181 pairs). It does **not** alter frozen matched cohorts, labels or historical C6 p-values.

The existing [nine-pair worst-case deletion bound](C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) shows that the direction of three important binary indicators cannot reverse under *any* nine-pair removal. That is a post-hoc aggregate bound, **not** the actual restricted sample, an original multi-category Stuart–Maxwell retest, a multiplicity-adjusted conclusion or causal evidence.

## Mechanism-level issue/PR mismatch

The four late-issue scanner-positive cases have **14 original D1 root decisions**, including **eight of 43** unresolved D/D7 classification conflicts. In two mixed-feature PRs, cases 5264 and 5267, **all twelve scanner-producing roots** are in workstreams distinct from the linked issue's specific correction.

In case 5267, for example, the later issue asks for an old SQLite schema migration fix, and the PR genuinely adds that fix after the issue was created. Yet seven scanner-producing roots involve a separate version-preview feature, not migration. A PR closing an issue is therefore insufficient to infer that issue text instructed *every* root. This is a concrete issue-to-root construct-validity concern.

The disagreement concentration is **8/14 = 57.1%** in the four late-issue positive cases' roots versus **35/328 = 10.7%** in other roots. This is descriptive, post-hoc and **not an independent-root hypothesis test**: multiple roots belong to one PR. None of the 43 disagreements has been adjudicated by this finding.

## Reporting and repair

Treat the 3,809 units as **linked GitHub issue–agent-associated PR workflows**, not as 3,809 proven prospective agent prompts. For any strong mechanistic or prevention claim, add an independently coded, chronology-safe issue-to-root coverage variable:

1. Did the linked issue exist before PR creation?
2. Did it exist before the specific root-introducing commit?
3. Is the exact issue wording as of that commit recoverable and verified?
4. Does that wording cover this root's workstream: directly requested, necessary implementation dependency, unrelated workstream or indeterminate?
5. Were other issue links, agent prompts or reviewer instructions available earlier?

Preserve the complete 342-root census, 190 matched pairs and frozen D/D7 labels. Label missing evidence **unknown**, never automatically negative. Do not retrain or recode historical outcomes until independent annotation and review procedures are in place.

## Executable reproduction

From the private repository checkout, without private inputs:

~~~bash
python -m analysis.c1_c2_late_issue_chronology_gate
python -m unittest tests.test_c1_c2_late_issue_chronology_gate -v
~~~

When authorized original CSV byte copies can be placed outside Git:

~~~bash
python -m analysis.c1_c2_late_issue_chronology_gate --c1 "/absolute/private/C1_CASE_SCANNER_OPPORTUNITY_3809.csv" --c2 "/absolute/private/C2_MATCHED_PAIRS_FROZEN.csv"
~~~

The optional source validator refuses wrong byte lengths, unexpected SHA-256 hashes, symlinks, duplicate case IDs, positivity mismatches, invalid control membership and changes to the nine-pair intersection. The committed-only mode is **recorded-count/ID-consistency**, not original-byte replay.

The original **final August 29 SQLite SHA-256**, exact issue edits at root introduction, C6 raw paired master, 43 D/D7 disputes and 14 original O/W/P baseline SARIF files remain scientific release blockers. Neither Wits jobs/files nor historical labels were changed. This record contains no original source CSV or SQLite bytes.
