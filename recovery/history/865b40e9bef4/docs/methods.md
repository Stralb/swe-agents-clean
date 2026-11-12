# Methods and results

## Study design

The recorded dataset contains 3,809 linked issue-to-PR workflows, including 192 scanner-positive workflows. The matched comparison uses 190 positive workflows, each paired with one scanner-negative control. There are 115 same-repository matches and 75 cross-repository matches.

The unit of analysis is a matched workflow pair. The separate producing-change and root analyses have different units: 455 mapped changes in 191 workflows, grouped into 342 roots.

## Statistical analysis

Five categorical comparisons use Stuart-Maxwell tests. Three binary comparisons use exact McNemar tests. The issue-to-PR delay comparison uses a paired Wilcoxon signed-rank test. The nine-test family is adjusted using Holm's method.

Review status has 189 complete pairs, prior repository activity has 187, and the remaining comparisons have 190.

## Main results

| Measure | Scanner-positive | Control |
| --- | ---: | ---: |
| Explicit issue instruction | 121/190 (63.7%) | 148/190 (77.9%) |
| Issue suggests a solution | 33/190 (17.4%) | 9/190 (4.7%) |
| PR aligned with issue goal | 160/190 (84.2%) | 183/190 (96.3%) |

Instruction specificity differs in the full matched sample (paired p = 0.000520, Holm-adjusted p = 0.004681). Goal alignment also differs (paired p = 0.001019, Holm-adjusted p = 0.008149).

In the same-repository subset, the source-reported instruction-specificity p-value is about 0.00645. Goal alignment is less stable at about 0.077. The remaining seven primary comparisons were not statistically significant at 0.05.

These are observational associations. Matching does not remove all differences in task difficulty, repository conventions, or scanner coverage. The results do not establish that issue wording caused a warning or that a warning corresponds to a confirmed vulnerability.
