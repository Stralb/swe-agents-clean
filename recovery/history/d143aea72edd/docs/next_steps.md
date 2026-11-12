# Discussion agenda and next analyses

The matched sample supports two descriptive associations: lower issue-instruction specificity and lower PR goal alignment among scanner-warning-associated workflows. The central open question is whether these differences identify **missing task information** that is genuinely relevant to warning-producing implementation choices.

## Suggested next steps

1. **Freeze source provenance.** Obtain the exact original 190-row C6 master, authenticate its SHA-256, and regenerate the paired and repository-blocked uncertainty estimates from preserved row-level matches.

2. **Audit source-specific chronology.** For any prospective information claim, compare issue creation and as-of-commit issue content with the commit that introduced the *particular warning-producing mechanism*, not just the PR's earliest implementation commit. Record missing and mixed cases.

3. **Reconcile root annotation versions.** Locate the true earlier D-final root labels and coder/adjudication evidence. Explicitly resolve the 43 historically documented differences before discussing definitive mechanism-tier prevalence.

4. **Design a bounded counterfactual.** On a predeclared sample of historical warnings, intervene on the original issue using retrospectively available warning information, regenerate patches and compare both targeted-warning incidence and functional correctness. Reduce hindsight information in subsequent ablations. Call this an **oracle-assisted preventability experiment**, not a deployable agent workflow.

## Questions for supervision

- Should the research contribution centre on the observed issue/PR associations, the prospective mechanism/chronology audit, or the causal oracle-style intervention?
- What is the acceptable unit for the next experiment: matched workflow, root mechanism, individual introduced warning, or patch attempt?
- Which forms of historical warning information are permitted as counterfactual inputs, and which should be withheld as hindsight leakage?

These decisions should precede any large-scale implementation or final causal claim.
