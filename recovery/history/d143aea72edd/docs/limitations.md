# Validity and limitations

This is a **preliminary, supervisor-facing research snapshot**, not a paper-ready replication archive. The boundaries below are material to the contribution.

1. **Scanner finding versus actual vulnerability.** Scanner-positive denotes the study's recorded introduced-warning criterion. Warnings are not independently demonstrated exploitable defects or end-to-end functionality failures. Original CodeQL/other baseline SARIF and exact scanner-pack provenance still require full archival verification.

2. **Original file authentication.** A complete indexed representation of `C6_MATCHED_PAIR_MASTER_190.csv` was read (190 pairs), and eight paired outcomes were independently recalculated. The exact **98,431-byte** raw original CSV could not be materialized through the available Library interface, so its independent SHA-256 identity is not established. The original 190 signed delay differences and bootstraps are not bundled.

3. **Residual confounding.** Matching cannot guarantee equivalent underlying tasks, issue difficulty, repository practices or maintainer behavior. The weaker same-repository goal-alignment p-value warrants caution.

4. **Root coding provenance.** A separate D7 root-census representation contains **342** classified roots (233 M, 103 T, 6 H). The earlier file labelled D-final in the Library contains the same tested final routes/tiers as D7, despite an earlier historical 234 M / 103 T / 5 H count and a 43-row version-difference ledger. The independent original adjudication record and the exact pre-D7 version need recovery. This package therefore excludes root-route proportions from the main inferential results.

5. **Mechanical lockfile concentration.** One unmatched workflow contains **36 package-version roots** associated with **131 distinct scanner finding IDs**. Different finding IDs may refer to the same CVE. Neither 36 roots nor 131 findings should be treated as independent agent decisions or vulnerabilities.

6. **Temporal eligibility.** The study's earliest feature-level commit is not always the introduction of the particular scanner-producing code. For `CAPHTECH/kiri` root `CROOT-00154-01`, the source-reported introduction was 02:38:57 UTC while the exact target line first appeared in an inspected commit at 02:55:56 UTC, **after** the linked issue was created at 02:39:26 UTC on 4 November 2025. This requires re-evaluation of its original pre-change issue eligibility; it does not prove the agent actually saw or used that issue.

7. **Causal prevention is untested here.** Rewinding a historical issue, adding information drawn from an observed warning, regenerating a patch and checking the warning would test a retrospective oracle intervention. It would not establish deployable advance warning prediction or real-world defect prevention without controls for chronology, functionality and alternative warnings.

**Presentation rule:** report reproduced aggregate test statistics distinctly from source-reported, not-yet-replayed effects. Keep original observations immutable; record any chronology or coding corrections in separately versioned audit artifacts.
