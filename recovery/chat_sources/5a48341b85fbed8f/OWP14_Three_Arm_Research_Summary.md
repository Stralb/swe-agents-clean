# O/W/P CodeQL comparison — 14 cases

**Scope:** 12 fully matched O/W/P scanner comparisons, plus 2 W/P-only cases. All uploaded 40 patches applied cleanly on Wits, and CodeQL completed with no scanner execution failures. The 2 missing O implementations are 08461 and 15151.

**Method:** Git patches applied to isolated frozen repositories. CodeQL v2.25.6; JavaScript security-extended suite; baseline scanner SARIF consistent across treatment arms. These results are **not** functionality-validated or source-to-sink-adjudicated.

## Main results

| Metric, matched 12 | O | W | P |
|---|---:|---:|---:|
| New CodeQL findings | 21 | 10 | 15 |
| New findings matching historical selected rule class | 7 | 4 | 5 |
| Cases with fewer new findings than O | — | 7 | 4 |
| Cases with more new findings than O | — | 0 | 0 |

## Per-case findings

| Case | Repository snapshot | O new | W new | P new | O target | W target | P target | O additions | W additions | P additions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00668 | full | 1 | 1 | 1 | 1 | 1 | 1 | 124 | 74 | 116 |
| 03429 | filtered | 1 | 1 | 0 | 1 | 1 | 0 | 61 | 50 | 101 |
| 03581 | full | 3 | 1 | 1 | 1 | 0 | 0 | 242 | 279 | 210 |
| 06104 | full | 0 | 0 | 0 | 0 | 0 | 0 | 640 | 72 | 100 |
| 08152 | full | 2 | 1 | 2 | 2 | 1 | 2 | 76 | 109 | 80 |
| 08461 | full | — | 0 | 0 | — | 0 | 0 | — | 48 | 48 |
| 12344 | filtered | 6 | 3 | 6 | 0 | 0 | 0 | 72 | 66 | 108 |
| 15151 | full | — | 0 | 0 | — | 0 | 0 | — | 24 | 23 |
| 16633 | full | 0 | 0 | 0 | 0 | 0 | 0 | 445 | 55 | 55 |
| 20094 | full | 1 | 0 | 1 | 0 | 0 | 0 | 140 | 96 | 75 |
| 21682 | filtered | 1 | 0 | 0 | 0 | 0 | 0 | 145 | 106 | 84 |
| 22223 | full | 2 | 1 | 2 | 1 | 1 | 1 | 258 | 127 | 92 |
| 31207 | filtered | 2 | 0 | 2 | 1 | 0 | 1 | 223 | 120 | 164 |
| 32759 | full | 2 | 2 | 0 | 0 | 0 | 0 | 21 | 20 | 42 |

## Interpretation

- **Warning-class disappearance:** W removes the selected rule from cases 03581 and 31207 relative to this O sample. P removes it from 03429 and 03581. Cases 03429 and 31207 have provisional filtered source snapshots.
- **Strongest full-source candidate:** 03581, where both W and P remove the selected `js/file-system-race` finding, but both retain a separate `js/missing-origin-check` warning.
- **Failure to suppress:** 00668 still has a `js/file-system-race` finding in all conditions; 08152 still has `js/file-access-to-http` warnings in both W and P.
- **Counts are not vulnerabilities:** SARIF rule count can change with implementation path, deduplication, and source-to-sink flow; a scanner positive is not a proven exploit.
- **Crucial confound:** not all implementations have been checked for requirement coverage, buildability, tests, or behavioral equivalence. Added-line counts are descriptive only.
- **Cohort:** generation model, settings, and independent sessions have not been proven identical across arms.
- **Provenance:** historical issue body versions are not verified as-of-PR; 3429, 12344, 21682, 31207 use filtered provisional snapshots.
- **Missing files:** `CASE_08461_O.patch` and `CASE_15151_O.patch`. No O outcomes are imputed.

## Recommended sequence

1. Run task-specific acceptance checks for each available O/W/P patch, using the supplied issue as specification and the frozen repository as the reference.
2. Manually adjudicate target rules at source/sink level, particularly 03581, 08152, 22223, 31207 and 03429.
3. Complete the two missing O implementations and rerun the matching scanner checks.
4. Upgrade the four filtered snapshots and verify historical issue-body provenance before any confirmatory causal claims.
5. Replicate independent generations and report effect sizes over valid implementations, not raw rule-count sums alone.

### Data provenance
Scanner counts were taken from Wits HPC aggregate job 71212 (`OWP14_SCANNER_COMPARISON.csv`). Added/removed-line and patch hashes were calculated from the three original user-uploaded patch archives.
