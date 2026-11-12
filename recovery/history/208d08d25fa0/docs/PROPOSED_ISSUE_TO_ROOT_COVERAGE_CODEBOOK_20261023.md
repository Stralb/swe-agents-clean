# Proposed issue-to-root relevance and chronology annotation protocol

**Version:** proposal v0.1, 23 October 2026.  
**Status:** prospective research design only. **Not frozen, not executed, and not a replacement for D0, C1/C2/C6, D-final or D7 labels.**

## Scientific problem

A merged agent-associated pull request may be linked to a GitHub issue even when the issue was created *after* the PR opened or when that issue describes only one of several PR workstreams. For example, the [full-cohort chronology audit](ISSUE_PR_CHRONOLOGY_WHOLE_COHORT_20261023.md) finds 49 issue-after-PR-creation links among 3,809 C1 workflows, including four scanner-positive cases and five post-merge issues; original C2 includes nine affected positive-control pairs. [The focused four-case analysis](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md) confirms two mixed-task PRs with twelve scanner-producing roots belonging to workstreams distinct from the linked issue's specific repair.

A wording-based association at the **linked-issue level** is not equivalent to an explanation of a **specific root implementation decision**, and neither establishes that the agent received the issue text as its original prompt.

## Separate constructs, units and observable fields

**Workflow record (C1/C2):** repository, PR number, issue number, PR creation time, issue creation time, PR merge time, observable issue–PR link provenance, and other linked issues. Do not equate PR creation with the beginning of all work or assume issue text remained unchanged.

**Root decision (D):** D1 root ID; the exact minimal source-diff operations participating in the root; first source commit introducing those operations (or unknown); one neutral implementation goal statement derived from code rather than scanner results; and the relevant PR workstream. One workflow may have several roots.

**Issue evidence snapshot:** immutable content and timestamp *before the root-introducing implementation commit* when available; separate current-body snapshot as lower-quality fallback with a warning that historical edits are unresolved. PR comments, review comments, issue edit histories and other linked tasks are individual potential evidence sources. Keep private prompts as unavailable unless actually preserved.

## Operational coding fields

| Field | Values | Decision criterion |
| --- | --- | --- |
| issue_at_PR_open | yes / no / unknown | Linked issue existed at or before PR creation timestamp |
| issue_at_root_introduction | yes / no / unknown | Linked issue existed at or before the earliest commit containing the root-producing step |
| issue_body_asof_root_verified | yes / no | A history-safe snapshot shows exactly the relevant text at/before root introduction |
| workstream_coverage | direct / necessary_dependency / unrelated / indeterminate | Whether the *root's workstream* is covered by the linked issue's stated task |
| mechanism_prescribed_by_issue | yes / no / indeterminate | If the issue covers the root, whether the text actually dictates this exact implementation mechanism among alternatives; do not infer from PR or scanner hindsight |
| earlier_independent_instruction | verified / plausible_not_verified / none_observed / unknown | Distinguish alternative public instructions from absence of evidence |
| source_evidence_grade | precommit_snapshot / timestamped_public_comment / current_public_only / missing | Highest available chronology-safe support; preserve all underlying sources |
| reviewer_A, reviewer_B, adjudicated_value | above categories + rationale | Never overwrite the original independent reviewer records |

**Direct:** issue explicitly requests implementing the same user-visible functionality or precise corrective behavior that the root serves. Mere lexical overlap is not enough.  
**Necessary dependency:** root implements indispensable supporting work for that requested goal, even if not explicitly specified; require a concrete dependency argument with plausible alternatives considered.  
**Unrelated:** root serves a separable feature/workstream, and the issue-specific goal could be completed without it.  
**Indeterminate:** multiple plausible tasks or insufficient chronology/commit or provenance make scope impossible to decide. This is a legitimate observation, not a coding failure.

The coverage classes above are *not* D0 categories H/T/M and are *not* the C6 instruction-specificity or PR-alignment codes. Do not remap or collapse labels across those codebooks without a separate validated operational mapping.

## Review, bias prevention and reliability

1. Freeze the source manifest and rules **before** annotating the remaining roots. Keep already investigated cases 5264/5267/7682/12334 as illustrative calibration examples only; do not use their conclusions as independent blinded evaluation outcomes.
2. Use the **342-root D1 census**, retaining all ambiguous, nonpositive, relabeled or disputed cases at their original provenance stage. If extending workflow-level C6 comparisons, code the original **190 paired positives and 190 controls** separately on the same issue–PR coverage rubric; a control workflow lacking a D root is not a negative root.
3. Give two independent coders issue text and timestamp, neutral root/PR diff material and allowed pre-root public context. Hide original scanner warning classifications, D-final/D7 labels, current study statistical outcomes and desired intervention outcome until after independent coverage coding wherever feasible.
4. Record every claim with exact URLs, commit SHA, creation/edit timestamps, relevant lines, source-availability status and independent rationale. Reviewer disagreements are preserved before adjudication. Require an independent adjudicator for material disagreements.
5. Report raw agreement and a chance-corrected coefficient (e.g. Cohen's kappa for nominal categories), the prevalence of unknown, source-missingness by stratum, and whether results depend on treating necessary_dependency as covered. Do not convert unknown to unrelated.
6. Release a blinded adjudicated coverage ledger separately from frozen D/D7 semantics; never update the old C1/C2/C6 scientific inputs or original D/D7 labels in place.

## Planned analysis, not retrospective result

**Primary descriptive audit:** fraction of linked issues not available by PR opening or root introduction, proportion unrelated/unknown at root level, and how these proportions vary by repository, root workstream and independently recovered source availability.

**C6 validity sensitivity:** recompute the original nine primary comparisons on source-authenticated paired C6 data with the prespecified coverage/chronology strata. Preserve all original 190 pairs in the historical table; use deletion, restriction and missingness bounds as transparently additional sensitivity. Apply the same multiple-testing treatment to *any* new primary family. Account for shared repositories and clustering rather than treating 342 roots as iid.

**Mechanistic inference:** only evaluate an issue's explanatory power for roots with verified issue coverage and adequate as-of-commit timing; treat the other roots as cases of missing or mismatched issue evidence. For prospective claims, show what information the developer/agent could actually have possessed before the implementation decision, not what later scanners or reviewers knew.

**Retrospective interventions:** restrict warning-informed hindsight conditions to clearly specified counterfactual oracle analyses, with separate prospective retrieval feasibility and functional acceptance. A vanished CodeQL alert is not sufficient evidence of a fixed vulnerability, equivalent functionality or causal prevention.

## Completion criteria for this new protocol

Before asserting that issue ambiguity contributes to a particular root selection:
- a stable frozen issue→root evidence manifest and creation/commit chronology;
- source-supported goal coverage or explicit indeterminate status;
- independent annotation records and adjudication provenance;
- authenticated original C6 paired labels, plus original study cohort and scanner source verification to support quantitative conclusions;
- separated scanner-warning, producing-change, root-decision, workflow and intervention-generation denominators.

**Current status remains PROPOSED.** No annotations for all 342 roots have been carried out, no prospective intervention has been executed, and no historical observation or original Wits file was modified.
