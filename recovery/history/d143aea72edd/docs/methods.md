# Methods

## Cohort and unit of analysis

The study associates GitHub issues with coding-agent-associated pull requests and examines static-analysis findings on the associated code changes. The recorded population is **3,809 linked issue→PR workflows**, including **192 scanner-positive workflows**. Matching retained **190 distinct scanner-positive workflows**, each paired with one scanner-negative control. Two scanner-positive cases were unmatched.

Matching was frozen before the C6 comparisons. Of the 190 pairs, **115 are within the same repository** and **75 use controls from another repository**. The primary statistical unit here is the **workflow pair**, not an individual warning, changed line, pull request file or scanner rule.

The root-level evidence study uses different units: **455 producing changes**, **342 grouped roots**, and **191 root-bearing scanner-positive workflows**. Those denominators must not be used interchangeably with the 190 matched pairs.

## Nine specified comparisons

The paired workflow analysis measures: issue purpose; instruction specificity; PR goal alignment; implementation category; formal human review before merge; issue→PR creation delay; whether requester and PR author are the same; whether the requester has prior repository activity; and primary coding-agent/tool classification.

Categorical outcomes use a **Stuart–Maxwell marginal-homogeneity test** based on the observed paired contingency table. The reported effect is **total variation distance** between the positive and control marginal category distributions.

Binary outcomes use the **two-sided exact McNemar test** on discordant matched pairs. The reported effect is the **positive-minus-control matched rate difference**.

Issue→PR delay uses a **paired Wilcoxon signed-rank test**. This snapshot reports the historical result but does not re-run it because the aggregate tables do not preserve the 190 signed delay differences.

## Missing values and multiplicity

Complete-case denominators are **189** for formal human review (one missing pair), **187** for prior repository activity (three missing pairs), and **190** for the other seven variables. Missing observations are not recoded to “No.”

Holm family-wise multiplicity adjustment is applied to **all nine** primary p-values. This includes the historical Wilcoxon p-value; the adjusted inference should be revisited if the full source data or specified family changes.

## Reproducibility boundary

The included aggregate contingency matrices were reconstructed from the full indexed C6 paired records and checked against the original omnibus output. Raw original CSV bytes have **not** been independently SHA-256 authenticated. Exact paired bootstrap and repository-blocked bootstrap confidence intervals require the original pair-level source and are **not** reconstructed here.

This matched design supports descriptive, adjusted-for-measured-matching comparisons. It does not randomize issue instructions or establish whether a changed issue would prevent a historical scanner finding.
