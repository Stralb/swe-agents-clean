# Preliminary matched-control results

**N = 190 matched positive/control workflows**, except where noted. Tests refer to scanner-warning association, not confirmed security exploitation.

| Comparison | Pairs | Effect (positive − control / TVD) | Paired p | Holm-adjusted p |
| --- | ---: | ---: | ---: | ---: |
| Issue purpose | 190 | TVD 0.1000 | 0.097193 | 0.680348 |
| **Instruction specificity** | 190 | **TVD 0.1421** | **0.000520** | **0.004681** |
| **PR goal alignment** | 190 | **TVD 0.1211** | **0.001019** | **0.008149** |
| Implementation category | 190 | TVD 0.1263 | 0.119524 | 0.717141 |
| Formal human review before merge | 189 | +0.0370 | 0.418754 | 1.000000 |
| Issue→PR delay (hours)¹ | 190 | Median paired difference −0.4049 h | 0.241232 | 1.000000 |
| Same issue/PR author | 190 | +0.0053 | 1.000000 | 1.000000 |
| Any prior requester repository activity | 187 | −0.0481 | 0.335558 | 1.000000 |
| Primary coding agent/tool | 190 | TVD 0.0579 | 0.219011 | 1.000000 |

¹ **Historical result only in this aggregate package**. The eight categorical/binary comparisons are recomputable from the provided sufficient statistics.

## Two main associations

**Instruction specificity.** The scanner-positive issues were less likely to contain an explicit instruction: **121/190 (63.7%)** versus **148/190 (77.9%)** in controls. They more often suggested a solution (**33/190** versus **9/190**). The three-category paired Stuart–Maxwell test has p = 0.000520; Holm-adjusted p = 0.004681.

**PR goal alignment.** The original positive PRs were less often coded as aligned with the linked issue: **160/190 (84.2%)** versus **183/190 (96.3%)** in controls. The four-category paired Stuart–Maxwell test has p = 0.001019; Holm-adjusted p = 0.008149.

These findings survive Holm adjustment in the nine-test family. The original **same-repository subset** retains a reported specificity association (p ≈ 0.00645) but the corresponding goal-alignment comparison is less stable (p ≈ 0.077). Same-repository analyses are sensitivity checks, not replacements for the full matched design.

## Non-findings and interpretation

No other primary outcome reaches p < 0.05 in the original paired tests. Absence of statistical significance does not establish equivalence between groups. Review frequency, response delay, prior activity and agent classification may still be affected by unmeasured variation or limited precision.

The observed differences are **associations in the matched observational sample**. An issue's explicitness may be correlated with task complexity, repository conventions, maintainers' practices or agents' implementations. The results do **not** establish that issue wording caused a scanner warning or that adding missing information would have prevented it.

Run `python3 scripts/reproduce_matched.py --check` for the exact aggregate calculation.
