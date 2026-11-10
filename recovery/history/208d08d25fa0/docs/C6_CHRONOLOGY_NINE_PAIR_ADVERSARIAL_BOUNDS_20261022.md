# C6 chronology sensitivity: adversarial deletion of any nine matched pairs

**Date:** 22 October 2026  
**Status:** `PASS_INDEXED_BINARY_WORST_CASE_DELETION_ONLY`

## Motivation

The live read-only [candidate-SQLite chronology replay](C1_C2_LIVE_CROSSWALK_AND_C6_SCALAR_REPLAY_20261022.md) identified **9 of 190 matched pairs** for which an issue creation timestamp falls *after* its linked PR creation timestamp on at least one side. Four positive cases and six controls show issue-after-PR ordering (one pair contains both). These observations are from the later continuation SQLite, **not an authenticated final 29 August database**. Any causal claim that issue content informed implementation is unsafe for these observations without chronology reconstruction.

The original C6 pair-level coding for the nine affected pair IDs is still unavailable. The three largest C6 categorical differences *are*, however, represented as complete **indexed aggregate matched-pair matrices**. Therefore we can compute a rigorously conservative bound without knowing which nine outcome pairs they were.

## Exact worst-case binary-category calculation

For each binary indicator (explicit instruction, suggests solution, aligned goal), reduce its 190 matched outcomes to three groups: positive-only `+1`, control-only `-1`, and both/neither `0`. Consider **every** valid way to remove exactly nine pairs. Recalculate the remaining 181-pair effect and exact two-sided binary McNemar p for each allocation. Keep the **largest p** and the minimum/maximum percentage-point difference.

| Indicator | Original (+1 / −1 / 0) | Original difference | Worst-case surviving difference interval | Largest possible exact binary McNemar p after removing 9 |
| --- | --- | ---: | ---: | ---: |
| Explicit instruction | 23 / 50 / 117 | −14.21 pp | **[−19.89, −9.94] pp** | **0.032766** |
| Suggests solution | 33 / 9 / 148 | +12.63 pp | **[+8.29, +18.23] pp** | **0.013531** |
| Aligned goal | 5 / 28 / 157 | −12.11 pp | **[−15.47, −7.73] pp** | **0.006611** |

The worst case for explicit instructions removes nine control-only pairs; for suggests-solution, nine positive-only pairs; for goal alignment, nine control-only pairs. In **every possible nine-pair deletion**, all three indicator *directions* are unchanged and their **separate exact binary McNemar tests remain nominally below 0.05**.

This is stronger than simply removing nine arbitrary numerator observations or assuming the affected nine have average outcomes. It is an exact finite combinatorial bound on all allocations consistent with the indexed source margins. The actual exclusion p-values are still unknown until the 190 pair-level semantic coding is available.

## Scientific limitations

1. **Not the original C6 omnibus tests.** The preregistered/frozen instruction-specificity and goal-alignment comparisons were multi-category Stuart–Maxwell tests, not binary-indicator McNemar tests. This audit **does not** reproduce those omnibus p-values after chronology exclusions.
2. **Not a replacement for nine-primary multiplicity correction.** The three highlighted binary category indicators were selected after seeing the archived interpretive findings; nominal p<0.05 is descriptive robustness only. In particular, these worst-case category p-values are **not** automatically significant under the historical nine-hypothesis family.
3. **Not final-source authentication.** These +1/−1/0 values come from indexed C6 aggregate tables, not independently SHA-matched original C6 paired CSV bytes. The number nine comes from a later continuation DB, not the frozen final SQLite.
4. **Not a security causal inference.** Keeping the association under nine deletions does not establish that vagueness caused vulnerabilities, that CodeQL warning introduction equals newly unsafe functionality, or that agent behavior would change when wording changed.
5. **Cannot validate actual nine-case exclusions.** This is an upper envelope over every nine-pair subset. The actual sensitive pairs may also have issue **text edits after PR creation** even if their issue was created earlier, requiring a different exposure definition and potentially more exclusions.

## Reproduction and release gate

From the private repository checkout:

```bash
python -m analysis.c6_chronology_deletion_bounds --remove-pairs 9
python -m unittest tests.test_c6_chronology_deletion_bounds -v
```

- The code reads the existing `provenance/c6_c7_indexed_aggregate_matrices_20261022.json` and `provenance/c6_indexed_main_pair_bootstrap_ci_20261022.json`, enforcing the previous indexed counts and unauthenticated-source flags.
- It imports the exact two-sided McNemar implementation from `analysis/c6_binary_conditional_gate.py`. All scenarios and summary output contain **only aggregate numbers**, no private root IDs or paired labels.
- **Next mandatory scientific step:** recover the original C6 matched-pair master; identify the nine affected pair IDs and their three semantic indicators; calculate actual restricted-sample multi-category omnibus tests and same-repository sensitivity; then widen chronology screening to edited issue descriptions.

This bound reduces sensitivity to known issue-after-PR records, but leaves the scientific source, scanner interpretation and causal intervention release gates open.
