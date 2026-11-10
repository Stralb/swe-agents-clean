# C6 paired-bootstrap distribution check — indexed aggregate inputs only

**Date:** 22 October 2026  
**Status:** `PASS_INDEXED_C6_ANALYTIC_PAIR_BOOTSTRAP_DISTRIBUTION_CHECK_ONLY`

## Question tested

Does the C6 source-reported *ordinary pair-bootstrap* 95% interval for the three largest interpretive categories agree with the mathematical bootstrap sampling distribution implied by its **saved matched-pair contingency counts**?

Because each matched pair contributes a category-indicator difference of **+1**, **0**, or **−1**, the complete 3×3 or 4×4 contingency table gives the empirical distribution of those differences. We can calculate the distribution of a 190-pair bootstrap replicate by convolving that three-point distribution 190 times. This requires no private record-level data, no random seed and no choice of a bootstrap replicate count. It also cannot simulate the **repository-blocked** bootstrap, for which the pair-to-repository assignments are required.

The archive reports percentile intervals from a finite bootstrap. It does not preserve the original seed, number of resamples or percentile interpolation code in the accessible aggregate evidence; exact equality is **not** required to pass this sanity check.

## Results

| C6 category | +1 pairs (positive only) | −1 pairs (control only) | Observed difference | Exact empirical-bootstrap 95% quantiles | Source-reported pair-bootstrap 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Explicit instruction | 23 | 50 | **−14.21 pp** | **[−22.63, −5.79] pp** | [−22.63, −5.79] pp |
| Suggests solution | 33 | 9 | **+12.63 pp** | **[+6.32, +18.95] pp** | [+6.32, +19.47] pp |
| Aligned implementation goal | 5 | 28 | **−12.11 pp** | **[−17.89, −6.32] pp** | [−17.89, −6.84] pp |

The two intervals for explicit instructions match to floating-point precision. For suggests-solution and aligned goal, one reported bound differs from the exact empirical discrete inverse-CDF quantile by **one 190-pair increment, 100/190 ≈ 0.526 percentage points**. Such a small discrepancy is compatible with finite Monte Carlo resampling and/or percentile interpolation. Neither mechanism can be established without the original bootstrap code/settings; the check does not infer the historical number of draws.

## Computation and reproducibility

Let a category's pair differences have counts `plus`, `minus`, and `zero`. For each bootstrap draw the empirical probabilities are `plus/190`, `minus/190` and `zero/190`. Starting with a zero-sum PMF, calculate the signed-sum PMF for 190 draws with a three-term recurrence. The lower and upper 2.5% discrete inverse-CDF quantiles, divided by 190, yield the **analytic pair-resampling interval**. They do not establish a causal effect.

Run:

```bash
python -m unittest tests.test_c6_indexed_pair_bootstrap_ci -v
python -m analysis.c6_indexed_pair_bootstrap_ci
```

The new files are:

- `analysis/c6_indexed_pair_bootstrap_ci.py` — deterministic, standard-library-only PMF and checks.
- `tests/test_c6_indexed_pair_bootstrap_ci.py` — 16 synthetic, numerical and source-indexed regression checks.
- `provenance/c6_indexed_main_pair_bootstrap_ci_20261022.json` — three original *indexed* aggregate interval records and provenance limitations, not original source bytes.
- `provenance/c6_indexed_analytic_pair_bootstrap_result_20261022.json` — aggregate-only calculation output.

The original indexed C6 results come from `C6_CATEGORY_DETAILS.csv` and `C6_PAIRED_CONTINGENCY_LONG.csv`, not SHA-256-authenticated original files. Together with previous C6 modules, **64** relevant tests passed locally at commit preparation. GitHub CI needs independent confirmation after commit.

## Limits

- No original C4/C5 semantic coding was replayed and no original C6 CSV bytes were authenticated.
- This is a **post-hoc mathematical consistency check**, not a rerun of the original finite Monte-Carlo bootstrap or its historical seeding and quantile interpolation.
- No repository-blocked bootstrap is recreated, and the reported repository-blocked confidence intervals remain source-reported only.
- No new intervention effect, prospectively known CodeQL warning prevention, scanner correctness or causal conclusion is established.
- The nine-primary Holm/BH analysis in `docs/C6_PRIMARY_MULTIPLICITY_CATEGORY_AUDIT_20261022.md` remains a distinct post-hoc sensitivity analysis.
