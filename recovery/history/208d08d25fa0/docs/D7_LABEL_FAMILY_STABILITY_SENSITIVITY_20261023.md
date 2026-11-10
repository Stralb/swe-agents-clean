# D-final versus D7 label-family stability and sensitivity

**Audit date:** 23 October 2026.  
**Status:** verified consistency of the *pinned 43-row difference ledger*, **not** complete original D/D7 source replay, independent human adjudication or an inter-rater study.

**Reproduce:** `python -m analysis.d7_label_stability_gate` and `python -m unittest tests.test_d7_label_stability_gate -v`.

## What the audit authenticates

The source is the existing committed [43-row D versus D7 disagreement ledger](../provenance/d_vs_d7_label_differences.csv), pinned to the Git object blob SHA-1 `93761f8742be9e6171229d60f9498ced8ee3c555`. The [executable audit](../analysis/d7_label_stability_gate.py) verifies this exact blob identity, all 43 distinct root IDs, all `UNRESOLVED` dispositions, source category membership, transition count conservation and historical reported route totals D-final `H=5,T=103,M=234` versus D7 `H=6,T=103,M=233`.

**Limitation:** the difference ledger does not include the other 299 unchanged rows. The agreement calculations below are **conditional** on its 43 rows exhaustively and correctly representing differences in the original 342-root populations. The two original full classification datasets, coder/adjudication materials and transformation script have not been independently byte-authenticated here.

## Coarse route is more stable than fine-grained explanation

| Comparison of versions | Recorded agreement conditional on exhaustive ledger |
| --- | ---: |
| Top-level H/T/M routing | **341/342 = 99.71%** |
| Joint (route, explanation tier) labels | **299/342 = 87.43%** |
| T1–T5/INCOMPLETE tier among the 233 roots assigned M by both | **191/233 = 81.97%** |

The one route conflict is `CROOT-00649-01`: D-final `M/T1` versus D7 `H/NA`. The remaining 42 disagreements leave route M unchanged but choose a different explanation tier; 17 involve the special `INCOMPLETE` status. The 42 disputed tier labels are spread over 33 workflow IDs, while all 43 differences span 34 workflows.

**Do not call these rates inter-rater reliability.** D-final and D7 are versions/procedures with different evidence availability, not two blinded independent coders applied to an identical frozen annotation protocol. Agreement is a descriptive comparison of record versions, not Cohen's kappa, reproducibility of coder judgments or validated ground truth.

## Exact effect of version selection on disputed-category counts

| Category among 43 disputed roots | D-final count | D7 count | D7 − D-final |
| --- | ---: | ---: | ---: |
| H / NA | 0 | 1 | +1 |
| M / INCOMPLETE | 5 | 12 | **+7** |
| M / T1 | **16** | **3** | **−13** |
| M / T2 | 4 | 5 | +1 |
| M / T3 | 5 | 10 | +5 |
| M / T4 | 9 | 12 | +3 |
| M / T5 | 4 | 0 | −4 |
| **Total disputed** | **43** | **43** | **0** |

This is the main interpretive risk. Choosing D7 instead of D-final reduces the number of **direct reuse (T1)** assignments by thirteen roots **in the disputed set alone**. The 299 other unchanged roots would contribute the same count in both versions, if the difference ledger is complete. Thus the *overall change in total T1 count is also −13* relative to those otherwise unchanged roots, although neither overall historical T1 denominator can be independently computed from this difference-only ledger without the full classification files.

Within the disputed set, 19 individual roots are T1 under one of the two versions. If one temporarily assumes the canonical tier for each such root must be *one of its two recorded labels*, the unresolved T1 count lies anywhere from **0 to 19** (the ledger itself gives D-final 16 and D7 3). This range is an annotation-choice uncertainty envelope, **not** a statistical confidence interval. The true answer may lie outside the two historic assignments if new evidence establishes a third option.

## Consequences for the paper

1. **Top-level prevalence:** Report H/T/M numbers only with explicitly named version, source-reported denominators and provenance qualifications; one disputed root changes H from 5 to 6 and M from 234 to 233. The full census's source-level membership still needs reauthentication.
2. **T1–T5 results:** Treat subtype prevalence and any subtype-conditioned tests as **not release-ready**. Large within-tier drift is possible even while top-level route barely changes.
3. **T5 versus INCOMPLETE:** D7 changes all four contested D-final T5 roots from workflow 05267 to `INCOMPLETE`. The root packets show those four belong to the PR's earlier preview workstream rather than the linked migration fix. Lack of a documented precursor cannot be equated to a verified bounded search for no independent explanation.
4. **Issue-to-root validity:** The [whole-cohort chronology audit](ISSUE_PR_CHRONOLOGY_WHOLE_COHORT_20261023.md) documents 49 linked issues created after PR opening, including 4 scanner-positive workflows; the [four-case investigation](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md) locates 8 D/D7 disputed roots in 14 late-issue positive roots. This is an exploratory prioritization signal, not evidence that a specific D or D7 label is correct.
5. **Mechanistic causal language:** Neither route stability nor subtype disagreement confirms that a linked issue governed a root choice, that a newly introduced scanner finding is a newly introduced security flaw, or that a retrospective warning-informed patch prevents a real vulnerability.

## Priority closure

Retrieve exact D-final and D7 342-root CSVs and their input/output SHA manifests; independently rebuild the difference ledger and every route/tier distribution. Recover frozen D0 codebook and original coding rationales for all 43 conflicts. Treat H-versus-M and T1-versus-T3/T4 questions separately; preserve original independent labels, establish source-specific chronological and mechanism evidence, blind-adjudicate under frozen criteria, and version the resolution rather than overwriting historic data. Recompute any subtype-stratified findings only after that process.

**Original Wits artifacts, D-final/D7 labels, C1/C2/C6 observations and CodeQL evidence were not changed.**
