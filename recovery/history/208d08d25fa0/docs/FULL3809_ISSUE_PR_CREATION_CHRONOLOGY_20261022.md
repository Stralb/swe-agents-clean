# Full 3,809-workflow chronology: when the linked issue came after the PR

**Audit date:** 22 October 2026  
**Status:** `PASS_RECORDED_CROSS_SOURCE_CHRONOLOGY_ARITHMETIC_ONLY`. Source records checked from original C1/C2 plus a *later continuation* SQLite; the August 29 final SQLite SHA-256 remains unauthenticated.

[Small aggregate/ID-only provenance record](../provenance/full3809_issue_pr_event_order_20261022.json) · [Independent fail-closed bookkeeping gate](../analysis/full3809_event_order_gate.py) · [Four positive-case root-scope audit](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md)

## Question and the unit of evidence

A GitHub issue being **linked** to a merged agent-associated PR does not establish that (a) the issue existed when the PR began; (b) the agent received that issue; (c) the PR was entirely implementing the issue; or (d) a particular scanner-producing root was selected because of its text. The first point is partially checkable with simple timestamps, but the later three require root/commit-specific evidence. The study's C6 issue-text comparisons and retrospective instruction interventions especially need this distinction.

In a read-only Wits candidate-database join of the 3,809 original case IDs to their historical issue and PR timestamps, we queried six non-overlapping case-ID ranges. We retrieved all **49** case IDs with `issue.created_at > pr.created_at`; among these, **five** had `issue.created_at > pr.merged_at`.

### Reconcile timing against the original C1 source, not a database status flag

To avoid confusing mutable scanner status and frozen C1 outcome, the full original **841,710-byte** Wits C1 file `matched_control_c1_v1_1/C1_CASE_SCANNER_OPPORTUNITY_3809.csv` was separately read in chunks and partitioned into three non-overlapping byte ranges by CSV row starting positions. A small overlap at byte-range edges allowed any line crossing an edge to be read in full; every data row was assigned to **exactly one** original source byte segment. The full C1 header has 24 columns; `is_positive` is the frozen 10th column. C1 and C2 original SHA-256 hashes were independently checked against their manifests in separate earlier recorded passes, *not recomputed in this one*. No Wits files were edited or copied to Git.

| C1 source byte interval | Rows | C1 positives | Issue created after PR opened |
| --- | ---: | ---: | ---: |
| [0, 420000) | 1,919 | 69 | 29 |
| [420000, 630000) | 944 | 53 | 10 |
| [630000, 841710) | 946 | 70 | 10 |
| **Total** | **3,809** | **192** | **49** |

The candidate SQLite query ranges independently contribute 1,758 + 1,045 + 839 + 112 + 48 + 7 = **3,809** case rows and 27 + 12 + 6 + 0 + 3 + 1 = **49** issue-after-PR creations. The original C1 positive mapping shows:

| Full workflow group | Original C1 case count | Issue created after PR opened | Within-group proportion |
| --- | ---: | ---: | ---: |
| All linked workflows | 3,809 | **49** | **1.29%** |
| Frozen scanner-positive | 192 | **4** | **2.08%** |
| Frozen scanner-negative | 3,617 | **45** | **1.24%** |

The four late-issue positives are **5264, 5267, 7682, 12334**, the same four independently inspected in the [original root-level audit](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md). The other **45** are frozen C1 scanner-negative. The difference in rates is descriptive only and should not be used as an independently established risk factor: dates come from a later candidate SQLite, samples are repository/agent-associated, and causal linkage is unmeasured.

## Strongest chronological impossibility: five issues postdate PR merge

All **five** cases whose issue was created after their PR's recorded merge are **scanner-negative in the frozen C1 file**:

| Case | Linked issue | Merged PR | Event ordering |
| --- | --- | --- | --- |
| 11280 | [#628](https://github.com/alvinunreal/oh-my-opencode-slim/issues/628) | [#625](https://github.com/alvinunreal/oh-my-opencode-slim/pull/625) | Issue created **61 seconds** after merge |
| 16358 | [#1999](https://github.com/NapNeko/NapCatQQ/issues/1999) | [#1983](https://github.com/NapNeko/NapCatQQ/pull/1983) | Issue opened several days after merge |
| 16603 | [#15](https://github.com/luckyyyyy/miu2d/issues/15) | [#12](https://github.com/luckyyyyy/miu2d/pull/12) | Issue opened approximately one week after merge; issue and PR titles concern visibly different topics |
| 37310 | [#220](https://github.com/xiaotianfotos/homerail/issues/220) | [#113](https://github.com/xiaotianfotos/homerail/pull/113) | Issue opened over two weeks after merge; issue and PR titles differ |
| 44072 | [#720](https://github.com/webpack/webpack-bundle-analyzer/issues/720) | [#718](https://github.com/webpack/webpack-bundle-analyzer/pull/718) | Issue opened **4 minutes 22 seconds** after merge |

All five public GitHub issue/PR event timestamps were independently inspected in this audit, in addition to the Wits read-only candidate SQLite. A later issue **could not** have supplied instructions to an already-merged historical PR. But a post-hoc issue link is a source-selection/temporal-validity problem; it does not by itself imply that the original PR patch is malicious, insecure, or scanner-positive. Since these five are C1 negatives, they do not directly affect the positive-root census; it is still essential not to treat them as valid prospective issue-derived controls or examples without case-specific provenance.

## Confirm the nine original C2 matched pairs affected

Separately rereading the complete original 56,175-byte C2 matched-pair CSV and intersecting both its positive and control case IDs with the 49-item chronological source ID set gives **exactly nine affected pairs**. Four of the nine have a late positive-side issue, six have a late control-side issue, and **one pair is late on both sides**. Four affected pairs are Tier A same-repository and five Tier B cross-repository.

| Positive case | Control case | Tier | Late issue side |
| ---: | ---: | :---: | --- |
| 708 | 12343 | B | Control |
| 3340 | 3342 | A | Control |
| 5264 | 16296 | B | Positive |
| 5267 | 549 | B | Positive |
| 7682 | 17908 | B | Positive |
| 12334 | 12335 | A | **Both** |
| 17048 | 4410 | B | Control |
| 32759 | 32758 | A | Control |
| 33183 | 4021 | A | Control |

The earlier [nine-pair worst-case deletion bounds](C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) are thus anchored to the precise nine frozen C2 pair memberships, rather than a speculative count. Still, those bounds represent every *possible* nine-pair deletion for three **selected binary indicators**, **not** actual C6 case-level semantic recoding or the multi-category Stuart–Maxwell omnibus tests.

## Scientific interpretation: which issue-exposure claim is invalid?

**Cannot start the PR from a later issue.** For the 49 cases, the linked issue did not exist at the PR's opening. This is a conclusive temporal restriction from observed event times.

**Could a later issue inform a subsequent commit within that PR?** Yes. Forty-four of the 49 cases had linked issues created after PR opened but before merge. Case 5267 demonstrates this: the linked migration issue was created after a version-preview PR opened, then the migration fix was added in a separate commit before merge. The migration issue can explain that later schema fix, **but not automatically the seven unrelated preview roots**. Case 5264 similarly mixes LAN-peer mechanisms and a separate approval-memory fix. This requires actual commit introductions and true issue-as-of-introduction snapshots rather than excluding every late issue as irrelevant.

**Cannot influence an already merged patch.** For the five issues created after PR merge, that specific issue cannot be the historical instruction that produced that earlier merged patch. A retrospective link can still be observed and may be meaningful as later discussion; it is not pre-implementation task evidence.

**What still cannot be concluded:** no claim about the individual agent's private prompts, intent, whether static-analysis warnings correspond to newly introduced vulnerabilities, or whether removing any such cases causally changes issue-text comparisons. The original C6 paired labels remain inaccessible at authenticated byte level; the original final SQLite is also not independently authenticated. Keep all frozen C1/C2 cases unchanged and report this as an explicit **case-linked issue timing and mixed-workstream threat to construct validity**.

## Check rerun, additional source needs

From the private working PR checkout, run:

~~~bash
python -m analysis.full3809_event_order_gate
python -m unittest tests.test_full3809_event_order_gate -v
python -m analysis.late_issue_root_scope_gate
~~~

This audits the **recorded source-indexed outputs** without contacting Wits or shipping original data into Git. Next recover/re-hash the exact final frozen SQLite, extract issue and PR event history including edits, pin the linked issue's content at the time **each root was introduced**, and verify each root's issue-to-task coverage independent of scanner outcomes. Update a new versioned research ledger only after authorizing re-adjudication; original source labels remain immutable.

**Read-only assurance:** all Wits operations were query/read only. No original files, Slurm jobs, upstream GitHub repositories, dataset annotations, or frozen source-code changes were mutated.
