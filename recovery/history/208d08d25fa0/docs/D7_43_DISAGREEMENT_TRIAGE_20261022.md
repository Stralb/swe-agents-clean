# D-final versus D7: prioritized reconciliation of 43 disputed root labels

**Audit date:** 22 October 2026  
**Status:** `PASS_FROZEN_DIFFERENCE_LEDGER_TRIAGE_ONLY__NO_ADJUDICATION`

This document groups the already frozen [43-row discrepancy ledger](../provenance/d_vs_d7_label_differences.csv) into evidence-recovery work. **Neither set of labels has been overwritten.** Root decisions remain the scientific unit; grouping by linked workflow below is a retrieval efficiency aid, not a declaration that all roots in one workflow share a label.

## Backlog, distinguishing roots from workflows

| Disagreement class | Roots | Distinct workflow IDs | Release status |
| --- | ---: | ---: | --- |
| H versus M route conflict | **1** | **1** | Unresolved; direct chronology and mechanism prescription required |
| Tier disagreement involving INCOMPLETE on at least one side | **17** | **10** | Unresolved; establish bounded evidence availability and T5 completeness |
| Both sides have completed M-tier labels but disagree | **25** | **24** | Unresolved; independent coder adjudication and tier-priority policy |
| **Combined** | **43** | **34 unique workflows** | None adjudicated |

These workflow subgroup counts need not sum to the combined distinct-workflow count: one workflow contributes to more than one tier-disagreement class.

All 42 non-route differences leave the root as M. The one route conflict is CROOT-00649-01 (D-final M/T1, D7 H/NA); its direct public-source and scanner evidence is in [the focused inherited-code audit](D7_CROOT_00649_RELOCATION_ROUTE_AUDIT_20261022.md).

## Frozen directional tier-transition census (42 M roots)

| D-final → D7 | Roots |
| --- | ---: |
| T4 → INCOMPLETE | 6 |
| T1 → T3 | 6 |
| T1 → T4 | 5 |
| T3 → T4 | 5 |
| T1 → T2 | 4 |
| T5 → INCOMPLETE | 4 |
| T4 → T3 | 2 |
| INCOMPLETE → T4 | 2 |
| T2 → T1 | 2 |
| INCOMPLETE → T3 | 2 |
| T2 → INCOMPLETE | 2 |
| INCOMPLETE → T2 | 1 |
| T4 → T1 | 1 |
| **Total** | **42** |

Exactly **17/42** tier differences involve INCOMPLETE; the other **25/42** dispute the best explanation despite both sides assigning completed tiers.

## Prioritize ten workflow-level source retrievals for seventeen incomplete roots

- Workflow `05267`: four T5→INCOMPLETE roots: `CROOT-05267-01/02/04/07`.
- Workflow `05264`: three disputed roots.
- Workflows `06150` and `16476`: two each.
- Workflows `00181`, `00280`, `03582`, `03684`, `16396`, `20094`: one each.

**Chronology / task-scope priority discovered in later verification.** The [four-case issue-to-root audit](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md) establishes that the linked migration issue for workflow `05267` was created **after** PR #1086 had begun and that **all seven scanner-producing roots belong to the separate preview-update workstream**, not to the small migration fix added later. Thus four T5→INCOMPLETE disagreements here also require **task-level issue coverage and root introduction time**, not just more repository searching. The linked issue's title/body cannot automatically serve as explanatory prior context for the preview mechanisms. The four D-final and D7 raw labels remain unchanged.

These ten workflow-level source dossiers cover all seventeen INCOMPLETE-related conflicts. The original Wits D2-A evidence packets for `CROOT-05267-01/02/04/07` were directly read. They concern distinct code/root operations associated with network access, file updates and local request behavior in the same workflow. Each packet reports issue-title, requested-goal, patch and repository-search evidence as available, but **does not carry explicit chronology fields** or the optional explicit Phase7 correction evidence. These availability booleans alone do **not** prove that every chronology-safe channel required by the codebook was actually reviewed, or that D7's INCOMPLETE label must be correct.

In particular, frozen D0 prohibits assigning **T5 (no independent public explanation found)** when a materially applicable evidence channel has not been checked. Four T5→INCOMPLETE cases should therefore be inspected **first**, but adjudication still requires source-specific evidence and must not infer failure solely from a Boolean availability flag.

## Methodological ambiguity worth recording before adjudication

T1 direct reuse, T2 strong repository precedent, and T3 explicit pre-change guidance are different *types* of explanation and may co-occur. The frozen D0 codebook defines each, but a single final explanation-tier label may not uniquely identify which applicable channel dominates when several support a root. There are, for example, **6 T1→T3** and **4 T1→T2** transitions. Their existence is not automatically evidence that one coder ignored a valid channel.

Before changing historical classifications, retain the original two labels, gather evidence **blind to original scanner outcomes when feasible**, explicitly record the presence of each independently supported evidence channel, and document how competing channels were prioritized. The single-tier tie-break should not be silently engineered after observing the conflicting results.

## Practical source-by-source adjudication ledger

For each root, collect a sealed evidence manifest including: frozen D2 packet identifier and checksum; PR true-base/head commit identity; pre-PR issue/comment/instruction snapshots and edit timestamps; exact producing diff; repository precursor search; mechanism-level applicability; completeness of bounded chronology review; both original coding rationales; and independent reviewer decision with uncertainty. Where new evidence changes a classification, record a **separate versioned adjudication** and keep both D-final and D7 raw labels unchanged.

The complete 342-root census, 233-versus-234 M-route difference, 455 producing-change mappings, and all original frozen warning/scanner results remain distinct audit stages. There is no release clearance for root-subtype effects until these 43 disagreements are adjudicated or transparently sensitivity-bounded.
