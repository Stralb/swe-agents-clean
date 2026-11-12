# C6 nine-test multiplicity and category-effect reconciliation

**Audit date:** 22 October 2026  
**Status:** `PASS_INDEXED_CATEGORY_MARGINS_AND_POSTHOC_MULTIPLICITY_SENSITIVITY_ONLY`

## Evidence hierarchy

This additional audit builds on two existing **indexed aggregate representations**, not authenticated source bytes:

- `C6_PAIRED_CONTINGENCY_LONG.csv` (165 indexed contingency cells); five primary categorical and two secondary matrices.
- `C6_CATEGORY_DETAILS.csv` (37 indexed effect-category rows), independently containing category numerator/denominator values and percentage differences.
- The historical C6 report's nine **reported** primary p-values, preserved in `provenance/c6_c7_completed_source_catalog_20261022.json`.
- The preceding audit's independently recomputed **five** Stuart–Maxwell p-values from indexed matched categorical counts in `provenance/c6_c7_indexed_aggregate_matrices_20261022.json`.

**Neither C6 original file SHA-256, original pair-level semantic labels, four remaining primary tests, nor repository-blocked confidence interval sampling has been independently reproduced.** The two indexed tables are distinct views of archived output, but could share a common upstream coding error. No causal conclusion follows.

## Newly checked category-effect table

Every one of **37 / 37** indexed C6 `C6_CATEGORY_DETAILS.csv` records agrees with the relevant C6 paired-contingency row and column totals, denominator, rates and percentage-point difference. This includes **190 pairs** for six categorical variables and **189 complete pairs** for *Requester association*. That 189 denominator is **not** proof of the cause of its missing record, and must not be conflated with the separately documented single missing **human-review** observation (also analyzed on 189 pairs).

| Category/metric | Positive | Control | Difference, percentage points |
| --- | ---: | ---: | ---: |
| Explicit instruction | 121 / 190 | 148 / 190 | -14.21 |
| Suggests solution | 33 / 190 | 9 / 190 | +12.63 |
| Aligned implementation goal | 160 / 190 | 183 / 190 | -12.11 |

The original category table reports a repository-blocked 95% confidence interval of **[-24.75, -4.63] pp** for explicit instructions. This interval is quoted as historical evidence, **not regenerated**; the pair/bootstrap seed and repository-level observations are unavailable.

## Nine pre-identified primary tests: extra multiplicity sensitivity

The frozen C6 study reports nine primary comparisons. Treating those nine as a single family, this new audit *additionally* applies Holm (family-wise error rate) and Benjamini–Hochberg (FDR) adjustments to **source-reported rounded p-values**. These corrections are **not asserted to be historically preregistered**. The original five matched categorical p-values had already been independently recalculated from indexed contingency counts; the other four remain source-reported only.

| Primary comparison | Original reported p | Holm-adjusted p | BH-FDR-adjusted p |
| --- | ---: | ---: | ---: |
| Issue instruction specificity | 0.00052 | **0.00468** | **0.00450** |
| PR goal alignment | 0.001 | **0.00800** | **0.00450** |
| Issue purpose | 0.097 | 0.679 | 0.270 |
| Implementation category | 0.120 | 0.720 | 0.270 |
| Human review (189 complete pairs) | 0.419 | 1.000 | 0.471375 |
| Issue-to-PR delay | 0.241 | 1.000 | 0.3615 |
| Same issue/PR author | 1.000 | 1.000 | 1.000 |
| Any prior repository activity | 0.336 | 1.000 | 0.432 |
| Primary agent/tool | 0.219 | 1.000 | 0.3615 |

At alpha=0.05 **only specificity and goal alignment survive** both procedures. The conclusion is stable under conservative rounding uncertainty: specificity's upper original p bound is 0.000525, and goal alignment's is 0.0015. Multiplying each bound by 9 is still below 0.05, so both survive even conservative Bonferroni, independently of any swap in their ranking. Every remaining reported p-value has a lower rounding bound greater than 0.05.

A further calculation substituting the five *indexed*-recomputed categorical p-values while leaving the other four **reported only** gives Holm-adjusted **0.0046811** (specificity) and **0.0081494** (alignment). This hybrid is a sensitivity exercise, not complete original-source replication.

### Tier-A same-repository caveat

The original historical Tier-A report gives specificity p=0.00645 and alignment p=0.077 for the 115 same-repository pairs. This is a separate *reported* sensitivity analysis, whose original paired count table is not authenticated here. It should not be merged into the full 190-pair primary family. If a hypothetical nine-test Bonferroni correction were imposed *separately* on Tier-A specificity, it would equal **0.05805**, but the historical Tier-A testing-family definition has not been established; this number is **not** a formal rejection of the original sensitivity result.

The strongest defensible statement remains: **the observational association with issue instruction specificity survives the full-cohort matched test, and its historical nominal same-repository sensitivity remains supportive**. Goal alignment is weaker because its same-repository sensitivity is not nominally significant. None establishes that underspecified issues cause scanner warnings or that the historical CodeQL rules were preventable prospectively.

## Reproducibility

The following files contain only aggregate counts and test metadata, without issue text, private case IDs or repository identities:

- `provenance/c6_indexed_category_and_family_20261022.json` — independent, indexed category-effect counts, seven paired contingency matrices' metadata (five primary from the earlier aggregate file; two secondary here), and historical p-value family.
- `analysis/c6_primary_family_audit.py` — deterministic standard-library Holm/BH implementations, source-to-source 37-row paired margin check, rounding-sensitive significance check, and strict missingness/provenance assertions.
- `tests/test_c6_primary_family_audit.py` — 22 synthetic and indexed-aggregate checks; errors are intentionally fail-closed.
- `provenance/c6_primary_family_adjustment_result_20261022.json` — generated aggregate-only replay output.

Commands from the repository root:

```bash
python -m unittest tests.test_c6_primary_family_audit -v
python -m analysis.c6_primary_family_audit --json
```

All 22 new tests, plus all 26 earlier indexed C6/C7 tests, passed locally during preparation. GitHub CI status must be checked separately on the committed head.

**Remaining blockers:** original C4/C5/C6/C7 source-byte authentication; four missing paired primary tests and repository-blocked resampling; exact final August 29 SQLite; original CodeQL baselines; 43 D/D7 root classification conflicts; historical counterfactual outcomes. Preserve the previous source-access restriction and leave the original Wits files immutable.
