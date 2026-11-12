# Methods and results

## Study population

The source-recorded cohort contains 3,809 linked GitHub issue-to-pull-request workflows. Under the original scanner-opportunity rules, 192 workflows were classified as scanner-positive and 3,617 as potential controls.

The matched analysis uses 190 distinct positive workflows, each paired with one scanner-negative workflow. Two positives were unmatched. Source records describe one-to-one matching without replacement. Of the 190 pairs, 115 are within the same repository with a compatible scanner-opportunity superset; 75 use a control from another repository with the same scanner-opportunity signature. The recorded matching procedure uses time and change-size restrictions, but the original matching optimizer is not included here.

The workflow pair is the unit of analysis for the comparisons below. The separate code-change analysis records 455 producing changes in 191 workflows, grouped into 342 implementation roots. These are different populations and must not be treated as interchangeable denominators.

## Paired comparisons

Five categorical comparisons use Stuart-Maxwell marginal-homogeneity tests. Three binary comparisons use two-sided exact McNemar tests. Issue-to-PR delay uses the paired Wilcoxon signed-rank test. Holm adjustment is applied across the nine primary comparisons.

| Comparison | Complete pairs | Paired p | Holm-adjusted p |
| --- | ---: | ---: | ---: |
| Issue purpose | 190 | 0.097193 | 0.680348 |
| Instruction specificity | 190 | 0.000520 | 0.004681 |
| PR goal alignment | 190 | 0.001019 | 0.008149 |
| Implementation category | 190 | 0.119524 | 0.717141 |
| Formal human review | 189 | 0.418754 | 1.000000 |
| Issue-to-PR delay | 190 | 0.241232 | 1.000000 |
| Same issue and PR author | 190 | 1.000000 | 1.000000 |
| Prior requester activity | 187 | 0.335558 | 1.000000 |
| Primary coding agent or tool | 190 | 0.219011 | 1.000000 |

The repository recalculates the five categorical and three binary tests from paired aggregate tables. The delay p-value is carried from the historical result because its 190 signed differences are not in the bundled aggregate data.

## Main associations

Explicit instructions occur in 121 of 190 positive issues (63.7%) and 148 of 190 matched controls (77.9%). The positive issues suggest a solution in 33 cases (17.4%), compared with 9 controls (4.7%). The instruction-specificity association remains in the reported same-repository analysis (p approximately 0.00645).

The PR is coded as aligned with the issue goal in 160 of 190 positives (84.2%) and 183 of 190 controls (96.3%). The reported same-repository analysis is weaker (p approximately 0.077), so this association warrants additional caution.

The other seven primary comparisons do not reach p < 0.05 in the original paired analysis. Nonsignificance does not demonstrate equivalence.

## Interpretation

The comparisons are observational. Task complexity, repository conventions, uneven scanner opportunity, and other unmeasured differences may affect the results. The tests do not establish that issue wording caused any finding or that an issue edit would prevent it.

Scanner-positive refers to the study's recorded warning criterion. Neither exploitability nor malicious intent follows from this label. The input records and scanner baselines need separate verification before release-level claims.
