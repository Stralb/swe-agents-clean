# C6 binary primary comparisons: control-source missingness and conditional paired arithmetic

**Audit date:** 22 October 2026  
**Status:** `PASS_CLUSTER_CONTROL_MARGINS_AND_CONDITIONAL_EXACT_MCNEMAR_CONSISTENCY_ONLY`

## Evidence and separation of claims

The read-only Wits DCR connection inspected the full original 35,844-byte `c6_context_completion_v1_0/C6_CONTROL_CONTEXT_190.csv` and its `C6_CONTEXT_QC.json`, built from the frozen C2 control case IDs. The historical C6 discussion reports human review **28.6% vs 24.9%, p=0.419** and any prior repository activity **70.1% vs 74.9%, p=0.336**. The preserved C6 report explicitly says the human-review API failure was later corrected to missing (no imputation) and the comparison uses 189 complete pairs.

**Cluster-derived independent control margins:**
- Human reviews: 190 controls, 47 observed Yes, 142 observed No, **one failed GitHub reviews lookup** (HTTP 404). Valid observations: **189**.
- Prior repository issues/PRs by the issue author: 190 controls, 140 observed >0, 47 observed zero, **three unknown** owing to failed API/search lookups. Valid observations: **187**.
- Original context QC also reports one missing account age, one missing issue-author association and 569 recorded review events. The raw original control CSV marks the failed review lookup as "No"; **that is an extractor artifact, not evidence of zero reviews**.

These are **original control-side observations**. Original positive-side C6 binary labels, pairwise joints and the source C6 master bytes have *not* been recovered in an authenticated form during this audit.

## Which denominators are arithmetically consistent?

Among 189 complete pairs, the only integer numerators rounding to 28.6% and 24.9% at one decimal are **54 positive Yes** and **47 control Yes**. Independently, 47 control Yes values were observed in the 189 successful review API records.

Among 187 complete pairs, 70.1% and 74.9% correspond uniquely to **131 positive Yes** and **140 control Yes**. The latter agrees with the independently recovered 140 controls with >0 prior interactions. **Neither of these prior-activity rates is attainable by integer numerators over 190 pairs at ordinary one-decimal percentage rounding.** The old provenance catalog states `source_reported_n=190` for the prior-activity primary test; this must now be treated as a *conflict in documentation*, not as evidence that incomplete records were imputed. The exact original `C6_PRIMARY_OMNIBUS_RESULTS.csv` and `C6_MATCHED_PAIR_MASTER_190.csv` are needed to establish the historical executable denominator and missing-value treatment.

## Conditional exact two-sided McNemar reconstruction

Conditional on the historical rounded rates, p-values and **the assumption that the binary comparisons used exact two-sided McNemar/binomial tests**, enumerate every possible 2×2 matched-pair joint table respecting the marginal Yes counts. Then evaluate
`p = min(1, 2 * P(Binomial(b+c, 0.5) <= min(b,c)))`
for the discordant positive-only `b` and control-only `c`. At three printed p-value decimals, the respective matches are **unique**:

| Comparison | N | Both Yes | Positive Yes only | Control Yes only | Neither Yes | Exact conditional p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Human review | 189 | 23 | 31 | 24 | 111 | **0.418754188269** |
| Prior repository activity | 187 | 101 | 30 | 39 | 17 | **0.335557618234** |

Rounded to three places these exactly reproduce reported **0.419** and **0.336**. This does **not** uniquely prove that the original analysis actually used exact McNemar tests: asymptotic and continuity-corrected variants can be numerically similar at limited display precision, and the positive-side marginals themselves came from the historical summary. Treat these as **conditional source-to-source consistency checks**, not independently reproduced original pair-level statistics. The nominal p-values are null under either candidate table.

## Release blockers and correct citation language

- Read authentic original C6 pair-level master and primary results CSV; verify SHA and preserve missing values. The live cluster exposes the control-context source but not the C6 combined paired master at the accessible research root.
- Independently recalculate full positive/control pairwise joint tables, actual effective denominators, exact historical test formulas and repository-blocked intervals. Do not silently change archived observations.
- Amend historical results wording only after the original source confirms N=187 for prior activity; for now clearly mark the conflicting 190 denominator in the provenance catalog as a *source-reported but unverified field*.
- Preserve the nine-primary family and source-reported Holm/BH sensitivity calculations separately from these conditional checks.

The original Wits cluster and original C6 artifacts were not modified. No private case IDs or issue/PR content are stored in this repository document.
