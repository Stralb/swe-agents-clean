# C6 matched-pair categorical omnibus: independent aggregate recalculation

**Date:** 22 October 2026  
**Scope:** Five of nine frozen primary comparisons, from indexed paired contingency counts. **Not** a full reproduction from authenticated C6 original bytes.

The indexed representation of `C6_PAIRED_CONTINGENCY_LONG.csv` exposed 165 aggregate cells across five primary categorical and two secondary variables. Each of the five primary categorical square matrices sums to exactly **190 matched pairs**. The three shared outcome margins reconcile with the 30 records in the indexed `C7_PATHWAY_STRATA_COMPARISON.csv` (190 overall, 115 Tier A). These are **source-derived aggregate representations**, not newly authenticated raw CSVs, and contain no case-level content.

The original C6 reported p-values were independently reproduced mathematically using **Stuart–Maxwell's matched categorical marginal-homogeneity test** (generalized McNemar), with the asymptotic chi-square survival function computed from the resulting covariance without treating the groups as independent:

| Frozen C6 comparison | Chi-square | df | Independently computed p | Historical reported p |
| --- | ---: | ---: | ---: | ---: |
| Issue purpose | 9.313549062 | 5 | **0.097192566** | 0.097 |
| Instruction specificity | 15.122913505 | 2 | **0.000520117** | 0.00052 |
| Goal alignment | 16.227074236 | 3 | **0.001018674** | 0.001 |
| Implementation category | 10.124067054 | 6 | **0.119523583** | 0.120 |
| Primary agent/tool | 7.021980761 | 5 | **0.219010697** | 0.219 |

The method is identifiable because the Stuart–Maxwell results match the original five reported significance levels; an independent Bowker symmetry test does **not** yield the same p-values. This establishes the interpretation of the saved paired matrices **conditional on their indexed counts**. It does not establish that the original C6 author actually used this formula or that the private paired semantic labels were correct.

## C7 overlap and subgroup accounting

From indexed C7 pathway-strata rates, denominators and exact integer numerators, the three overlapping outcome margins are:

| Metric | Positive / matched control (190 overall) | Positive / control (115 same-repo Tier A) |
| --- | --- | --- |
| Explicit instruction | **121 / 148** | **77 / 95** |
| Suggests solution | **33 / 9** | **15 / 3** |
| Aligned goal | **160 / 183** | **103 / 112** |

All weighted C7 subgroup totals reconcile to C6's matching margins. C7 remains explicitly **exploratory**; no new confirmatory test or causal effect is inferred from the subgroup rates.

## Reproduction tooling

- `provenance/c6_c7_indexed_aggregate_matrices_20261022.json` contains **aggregate counts only**, transcribed from the source-indexed parsed tables; no issue/PR text, case IDs, repository identities or individual pair records.
- `analysis/c6_c7_indexed_omnibus.py` implements pivoted covariance solving and exact integer-df chi-square tails using only the Python standard library. It validates the five source-reported p-values and recomputes the C7 overlap.
- `tests/test_c6_c7_indexed_omnibus.py` contains mathematical regression fixtures and negative tests. CI tests **only aggregate and fabricated data**, not original Wits/Library source artifacts.

Commands from the repository root:

```bash
python -m unittest tests.test_c6_c7_indexed_omnibus -v
python -m analysis.c6_c7_indexed_omnibus replay-indexed
```

If a **separately approved immutable copy** of the original 14,591-byte C6 contingency CSV becomes available outside the repository, authenticate it using an **independently pre-established** original SHA-256 and require exact agreement with the indexed aggregates:

```bash
python -m analysis.c6_c7_indexed_omnibus verify-staged-c6 \
  "/secure/approved/C6_PAIRED_CONTINGENCY_LONG.csv" \
  "<ORIGINAL_PRE-ESTABLISHED_SHA256>"
```

The same principle applies to the original 5,831-byte C7 stratified aggregate CSV, with its own pre-established SHA-256:

```bash
python -m analysis.c6_c7_indexed_omnibus verify-staged-c7-strata \
  "/secure/approved/C7_PATHWAY_STRATA_COMPARISON.csv" \
  "<ORIGINAL_PRE-ESTABLISHED_SHA256>"
```

Neither strict staged-original command has **run on the original bytes**. Never fabricate or retrospectively accept a fingerprint generated after seeing a modified dataset as evidence of the historical frozen source.

## Still open

- Hash-verify the source C6/C7 original CSV/package bytes and separately check the frozen C5 pair-level coding.
- Reproduce the **other four of nine primary tests**, repository-blocked resampling, original CI seeds and Tier-A same-repo significance tests.
- Reproduce C7 PC/pathway assignments from original source evidence, rather than merely aggregate margins.
- Authenticate the exact final August 29 SQLite and historical scanner baselines; resolve the 43 D/D7 root-label conflicts before subtype-sensitive research claims.

**Scientific classification:** `PASS_INDEXED_CATEGORICAL_COUNT_ARITHMETIC_ONLY`. No intervention effect, scanner causal validity or independent full-paper replication claimed.
