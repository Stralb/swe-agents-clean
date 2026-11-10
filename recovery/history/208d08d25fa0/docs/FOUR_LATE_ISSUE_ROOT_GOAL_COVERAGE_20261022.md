# Four scanner-positive issue-after-PR cases: root-to-request coverage

**Audit date:** 22 October 2026  
**Status:** exploratory source-level validity audit, **NOT** historical C6 rerun, D/D7 adjudication, or proof of a particular agent's prompt.  
**Executable aggregate ledger:** [provenance/late_issue_four_positive_root_scope_20261022.json](../provenance/late_issue_four_positive_root_scope_20261022.json)  
**Fail-closed arithmetic checker:** [analysis/late_issue_root_scope_gate.py](../analysis/late_issue_root_scope_gate.py)

## Precise scientific question

The original study follows a GitHub issue associated with an agent-associated merged PR and asks whether instructions and context constrained the implementation mechanisms associated with scanner findings. A **PR-to-issue link is not automatically an issue-to-specific-root causal or semantic link**. A PR can begin before an issue, serve another feature, and incorporate the issue's requested fix in a later commit. These are genuinely distinct units: one PR, one linked issue, several task workstreams, and several security-producing roots.

A read-only join of frozen C2 pairs to the **later continuation** Wits SQLite identified **four scanner-positive workflows** for which the issue was created strictly after the PR began. This review cross-matched their **14 original D1 roots** and original blind-A D2 packets to the public PR file patches and linked issue goals.

Current GitHub issue and PR text is **not** a proven immutable snapshot as of implementation. PR creation dates and issue creation dates are factual event timestamps. For each case, whether the agent saw a separate earlier prompt remains unknown.

## All four verified issue-after-PR workflows

| Case | Issue created after PR began | Root count | D/D7 disagreements | Root-to-linked-issue evidence |
| --- | ---: | ---: | ---: | --- |
| 5264 | +6 h 10 m | 5 | 3 | Roots implement **LAN-peer command, socket, device and HTTP features**; linked issue asks persistent command approval choices, handled in separate bridge patch |
| 5267 | +9 m 44 s | 7 | 4 | **All seven** scanner roots implement **version-preview/update work**; linked issue asks a `session_usage.created_at` schema migration, patched later in separate file |
| 7682 | +23 h 48 m | 1 | 0 | PR combines Pi runtime upgrade and Windows installer fix; scanner root is process launch / bundled-runtime command-resolution path; exact issue relation requires tracing |
| 12334 | +59 m 33 s | 1 | 1 | Root arises in an ACP diagnostic test, related to the capabilities issue and PR; issue still postdates PR creation |
| **Total** | | **14** | **8** | Not homogeneous; avoid universal exclusion or automatic recoding |

The complete 342-root D1 CSV and frozen 43-row D/D7 ledger agree with this membership. **Eight of 43 conflicting labels** are among the 14 roots from these four workflows; **seven of 43** are among the **12 roots in two mixed-workstream PRs** (5264, 5267). The other 328 roots contain 35 disagreements. The descriptive disagreement shares are **8/14 = 57.1%** versus **35/328 = 10.7%**. This is not an iid-root causal experiment or a prespecified statistical hypothesis; roots are clustered by workflow.

### Case 5267: clear split between the linked migration fix and scanner-producing preview feature

Public canonical repository is now `EKKOLearnAI/ekko-studio` (Wits source identity recorded as `EKKOLearnAI/hermes-studio`). [PR #1086](https://github.com/EKKOLearnAI/ekko-studio/pull/1086) was created at **03:58:21 UTC, 28 May 2026**, titled *add version preview workflow*. [Issue #1087](https://github.com/EKKOLearnAI/ekko-studio/issues/1087) was created at **04:08:05 UTC**, reporting migration failure when older `session_usage` lacked `created_at`. The PR was merged at **04:30:50 UTC** and closed the issue.

The actual PR includes an issue-specific fix: [commit `2ef456e`](https://github.com/EKKOLearnAI/ekko-studio/commit/2ef456ef26da30318818bce59f94ceb117bcf6da), dated **04:25:51 UTC**, changes **`packages/server/src/db/hermes/schemas.ts`** from a no-default `created_at` column to `INTEGER NOT NULL DEFAULT 0`, and adds a legacy migration test. It is a legitimate follow-up repair and explains why the issue is linked to the merged PR.

**However, none of the seven scanner-producing roots is in the migration fix.** Original Wits D2 root summaries place every one of `CROOT-05267-01` ... `CROOT-05267-07` in `packages/server/src/controllers/update.ts` / preview workflow (network archive downloads, tag fetching, filesystem writes and logging, shell utilities, and loopback HTTP preview). The original provenance packet independently notes the large preview/update block appears in the PR before the linked migration issue. The issue has no stated goal covering that feature. This is **source-supported PR task-mixing**, not evidence that the issue instructed those seven roots.

Four of these seven roots account for D/D7 T5→INCOMPLETE disputes: `CROOT-05267-01`, `-02`, `-04`, `-07`. The correct explanation cannot be inferred from the migration issue merely because the PR closes it. **Original exact root-producing commit timestamps and authenticated issue-as-of-commit snapshots still require verification**.

### Case 5264: persistent approvals versus LAN-peer tools

[PR #1351](https://github.com/EKKOLearnAI/ekko-studio/pull/1351) started **09:24:59 UTC, 5 June 2026** as LAN-peer MCP tooling. [Issue #1352](https://github.com/EKKOLearnAI/ekko-studio/issues/1352), asking why the *Always allow command* choice still caused later approval prompts, arrived **15:35:11 UTC**. The PR was merged **01:06:53 UTC, 6 June** and closed the issue.

The PR does address that issue in a **separate bridge subchange**: `packages/server/src/services/hermes/agent-bridge/hermes_bridge.py` adds `execute_code` session/permanent approval memory, with a dedicated `docs/chat-chain-changes/2026-06-06-local-execute-code-approval-memory.md` note. But the five original scanner-producing roots are command spawning in the LAN-peer service, devices HTTP and WebSocket interactions, and device relation endpoints. Those are **LAN-peer feature mechanisms not described by the linked approval-memory issue**. Three roots (`CROOT-05264-03`, `-04`, `-05`) have D/D7 explanation-tier differences.

### Case 7682: linked installer bug embedded in a large runtime upgrade

[PR #206](https://github.com/companion-inc/feynman/pull/206) opened **30 July 2026 09:03:44 UTC**, upgrading bundled Pi runtime and several runtime subsystems. [Issue #207](https://github.com/companion-inc/feynman/issues/207) reported a Windows 11 one-line install/extraction failure on **31 July 2026 08:51:51 UTC**; the PR was merged **1 August** and explicitly addressed #207 plus other issues. The one original root, `CROOT-07682-01`, covers native-bundle child-process command/shell resolution. This could affect install/runtime behavior, but **its exact causal relevance to issue #207 remains unverified**.

### Case 12334: issue and change substantially align, but timing remains reversed

[PR #2011](https://github.com/getpaseo/paseo/pull/2011) opened **11 July 2026 21:17:01 UTC** to make ACP client capabilities configurable. [Issue #2012](https://github.com/getpaseo/paseo/issues/2012), opened **22:16:34 UTC**, describes precisely that behavior. The one root, `CROOT-12334-01`, concerns a new ACP capability diagnostic test that invokes a process. **The issue and PR goals are aligned**, so treating it as unrelated would be unwarranted; but the issue still cannot be assumed to be the instruction used to initiate the PR.

## Validity consequences and minimal adequate repair

1. Distinguish **workflow issue→PR association** from **issue→each root implementation** in the study's claim structure. Only the latter supports issue-text mechanistic explanations. A PR closing an issue does not guarantee all changed code addressed it.
2. For each root, annotate **linked issue covers this workstream: yes / no / indeterminate**, independently of the scanner warning outcome. Preserve ambiguous mixed-task cases, other co-existing issues, and reviewer disagreement. Preserve the original frozen labels; store this as a *new* prospective adjudication layer, not a retrofit.
3. For any retrospective pre-PR instruction intervention, require the issue text to exist and be accessible **before the scanner-producing root was introduced**; issue creation after PR opening need not exclude a later issue-specific patch, but **the exact root introduction timestamp** matters. Verify commit chronology and issue edits or assign unknown.
4. Re-estimate existing C6 comparisons after excluding **only** evidence-supported uncoupled issue/root workflows or explicitly relabeling them as a separate mixed-task stratum, not by opportunistically dropping scanner outcomes. Use the original C6 pair-level master and repeated repository-blocked sensitivity, preserving 190 original pairs.
5. Separate descriptive issue instruction specificity from causal explanation, since reported differences might partially represent irrelevant linked issue text for feature roots. Do not claim the small four-case audit explains the full effect: an earlier [adversarial nine-pair deletion bound](C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) preserves *binary direction* for three indicators but does **not** recompute the omnibus Stuart–Maxwell after exclusions.
6. Treat the high D/D7 dispute concentration as prioritization evidence only: root outcomes are non-independent, number of roots per case varies, and this subgroup was found post hoc. The 43 labels remain **UNRESOLVED**.

**Release consequence:** the mechanistic issue-to-root explanation and prospective issue-only intervention claims should remain blocked for mixed-task roots until the new source-timed coverage layer is complete. The cluster, underlying GitHub repositories, original code, C/D labels and previously frozen study files were never modified.
