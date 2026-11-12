# C6: exhaustive nine-pair removal bounds for the original primary omnibus tests

**Date:** 22 October 2026  
**Status:** `PASS_INDEXED_C6_EXHAUSTIVE_NINE_PAIR_OMNIBUS_BOUNDS_ONLY`. Original paired C6 master not SHA-authenticated; actual chronology-affected pairs' semantic labels not recovered.

[Analysis implementation](../analysis/c6_omnibus_chronology_deletion_bounds.py) · [Fail-closed unit tests](../tests/test_c6_omnibus_chronology_deletion_bounds.py) · [Full 3,809-case event chronology](FULL3809_ISSUE_PR_CREATION_CHRONOLOGY_20261022.md)

## Scientific reason for re-running the original omnibus

The original C6 research examined **190 matched positive/control pairs** with primary matched **multi-category Stuart–Maxwell tests**, not separate binary tests on favorable outcomes. The original indexed tables had:

- **Instruction specificity (3 classes):** matched omnibus chi-square 15.1229135, df 2, p=**0.000520117**.
- **PR goal alignment (4 classes):** matched omnibus chi-square approximately 16.2270742, df 3, p≈**0.001018674**.

The earlier [binary indicator deletion bounds](C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) showed direction and nominal binary significance survived any nine-pair removal, but this was **not a test of the frozen multi-category omnibus outcomes**. The [full-cohort original C1/C2 timing crosswalk](FULL3809_ISSUE_PR_CREATION_CHRONOLOGY_20261022.md) now establishes exactly **nine** original matched pairs with a linked issue created later than its PR opening in at least one arm. We still lack the original C6 semantic category for each of those nine, so cannot produce the *actual* restricted-sample matrix.

Instead, conservatively remove **any nine pair observations** from the **indexed complete 190-pair contingency**, enumerate every feasible integer cell-level allocation, and recalculate the **same** Stuart–Maxwell test whenever its fixed covariance rank survives. This upper-bounds the worst case without selecting the nine cells to favor a result.

## Exact finite enumeration — every feasible nine-deletion allocation

| Frozen primary omnibus | Original p | Feasible nine-pair removal allocations | Fixed-category test computable | Worst computable fixed-category p |
| --- | ---: | ---: | ---: | ---: |
| Instruction specificity (3 classes) | **0.000520** | **8,006** | 8,006 / 8,006 | **0.019270** |
| PR goal alignment (4 classes) | **0.001019** | **2,788** | 2,136 / 2,788 | **0.039339** |

For **instruction specificity**, all 8,006 possible retained 181-pair contingency tables preserve the full-rank 3-class test and yield nominal **p below 0.05**. The weakest compatible result is obtained by deleting nine "Suggests solution" (positive) → "Explicit instruction" (control) paired cases. This is stronger than the earlier single-indicator robustness bound, because the **original 3-class omnibus** itself remains nominally significant under every possible nine-pair omission.

For **goal alignment**, all 2,136 allocations preserving all four observed categories yield nominal **p below 0.05**. The weakest full-rank result deletes **two Diverged→Aligned**, **six Expanded→Aligned**, and **one Unclear→Aligned** pairs. Here **652 feasible allocations remove both of the only two "Unclear" positive observations**, leaving that fourth category with zero row and zero column marginal. Then the covariance of the original fixed-four-category procedure is **singular**; it is scientifically incorrect to assign an ordinary df=3 original test p-value to such a table.

### Explicit, separate rank-adaptive sensitivity for 652 singular possibilities

As a **new post-hoc sensitivity method, not the historical fixed four-class analysis**, remove only categories that are completely absent in the surviving table (zero row **and** zero column totals). For this source, the sole disappearing category is **Unclear**. The remaining three classes form a valid 3×3 paired contingency with df=2.

Across all **652** such cases:

- The largest rank-adapted p-value is **0.016841**.
- All 652 remain nominally below p=0.05 under this explicitly stated new rank-adaptive procedure.
- The worst case removes two Diverged→Aligned, five Expanded→Aligned, and both Unclear→Aligned records.

Combining the fixed-rank and rank-adapted sensitivity schemes yields nominal significance in all 2,788 hypothetical exclusions. **However, this does not establish robustness of the original frozen four-category test in the 652 singular scenarios**, because that exact test is mathematically undefined after deleting the rare category.

## Exact method and important boundaries

For a k×k matched table N, row totals r and column totals c, define dᵢ=rᵢ−cᵢ and the first (k−1)×(k−1) Stuart–Maxwell covariance

- diagonal Vᵢᵢ = rᵢ + cᵢ − 2Nᵢᵢ;
- off-diagonal Vᵢⱼ = −(Nᵢⱼ + Nⱼᵢ).

For full rank, compute X² = dᵀV⁻¹d with df=k−1 and chi-square survival probability. This calls the **existing original indexed replay implementation**, not a new approximate test. Each allocation reduces nonnegative integer cell counts by a total of nine while leaving **181** matched pairs. Enumeration is exhaustive over feasible **cell removal counts**; there are many underlying identity-level subsets, but the test depends only on these counts.

**Claims these results do not support:**

1. **Not actual nine-case exclusion results.** The deleted pair IDs are known from the source chronology, but their C6 semantic categories and cross-variable dependence are not recovered from authenticated original C6 master bytes. Worst-case allocations for the two variables need not correspond to the *same* nine underlying pair IDs.
2. **Not familywise-adjusted robustness.** The original C6 nine-test family had two Holm-significant omnibus results; worst-case individual nominal p<0.05 does **not** establish that these would survive Holm adjustment after chronology exclusions. Other seven hypotheses' post-deletion p-values were not recomputed.
3. **Not originally preregistered adaptive categories.** The rarity-induced df change for goal alignment is a separate sensitivity procedure, clearly labelled as such.
4. **Not complete data source authentication.** The C6 matrices here are independently reconciled *indexed aggregate contingency counts*. The original `C6_MATCHED_PAIR_MASTER_190.csv`, exact original final SQLite snapshot SHA, repository-blocked confidence intervals and exact original C6 computation environment remain unavailable in authenticated form.
5. **Not causal proof.** The historical warning in coding-agent PRs may reflect moved pre-existing code, unrelated feature work, matched workflow confounding, or other safety mechanisms. This analysis cannot prove that ambiguity or issue wording *caused* a vulnerability.

## Reproduction

From the current private working PR, without external datasets:

~~~bash
python -m analysis.c6_omnibus_chronology_deletion_bounds --remove-pairs 9
python -m unittest tests.test_c6_omnibus_chronology_deletion_bounds -v
~~~

The code is deterministic, read-only and standard-library-only; it reuses `analysis/c6_c7_indexed_omnibus.py` for full-rank Stuart–Maxwell and chi-square probabilities, enforces frozen input matrices and unauthenticated-source provenance flags, and fails closed if any non-empty-category table remains singular. New source or sample values cannot be quietly passed off as historical C6 output.

## Interpretive takeaway

The *frozen indexed instruction-specificity primary omnibus* remains **nominally significant in every possible nine-pair chronological exclusion**, providing a defensible sensitivity bound even though the original case-level labels are unavailable. Goal-alignment's analogous sensitivity holds nominally under a clearly declared rare-category rank adaptation, while the original four-class test is undefined for 652 permissible exclusions. This is more informative than reporting the original p-values alone, but **does not resolve the C6 source authentication, issue-to-root construct validity, multiple-comparison, or causal interpretation release gates**.
