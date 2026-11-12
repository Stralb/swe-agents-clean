# C2 optimality bounds and permission boundary — 22 October 2026

## Verified CI

At branch commit `36b582e492fab23abd37e59822afd2e3b8f64588`, all eight GitHub workflow runs concluded successfully, including the reproducibility test suite and synthetic external-scanner smokes.

## Cardinality certificate versus lexicographic optimality

The full original frozen `C2_CANDIDATE_COUNTS_192.csv` has 192 positive rows, of which 190 have at least one source-recorded candidate and two (13918, 17460) have none. The selected pairs contain 190 distinct positives and controls. **Conditional on this table**, maximum cardinality = 190 and the frozen assignment reaches this bound.

Of the 192 source-recorded positives, **119** have at least one Tier-A same-repository candidate: the selected matching uses **115** Tier-A controls and **75** Tier-B controls. Thus `115 <= optimum_TierA <= 119` **if** the original candidate graph and lexicographic objective are correct. This *is not* proof that 116–119 Tier-A matches are jointly feasible: distinct controls may be contested. Of the 119 positive cases with Tier-A eligibility, 30 have exactly one such candidate, 26 have 2–3, 29 have 4–10, and 34 have more than 10. Case `4811` has at least one Tier-A candidate and no Tier-B candidate. The selected matched-pair calculation tables have already been independently reproduced, but a minimum total distance result is still unproven.

## Blocked full candidate-edge rederivation

The prior session began a batched C1 cohort replay: 1,346 complete rows, including 1,302 negative controls and 44 positives, were evaluated in the first window. That **partial** run cannot certify the source-reported 87,706 candidate edges or every positive's candidate-degree totals. The next attempt to access the original C1 artifact was rejected by the access service as approval/login declined. Do **not** retry that denied access path, infer authorisation, or claim the C1 replay complete. Resume only after an explicit authorised access change, or use separately provided approved copies.

## Scientific limits

This memo addresses matching **stored-record integrity and candidate upper bounds only**. It does not independently regenerate 192 scanner-positive labels from the original final SQLite; rerun the historical scanner baseline; prove maximisation of Tier-A matches or minimisation of total distance; reproduce the manuscript statistics; or establish counterfactual preventability or causal effects.
