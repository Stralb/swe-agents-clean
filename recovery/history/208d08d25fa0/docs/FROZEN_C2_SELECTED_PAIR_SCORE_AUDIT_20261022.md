# C2 selected-pair metrics and caliper audit — 22 October 2026

**Result:** 190/190 selected pairs reproduced with **zero** time, changed-size, logarithmic-ratio or distance discrepancies. This is a **selected-pair arithmetic verification**, not proof of global matching optimality or scanner outcome correctness.

The frozen C2 source defines:
```
days = |positive_PR_time - control_PR_time| / 86400
line_delta = |log1p(positive_lines) - log1p(control_lines)|
file_delta = |log1p(positive_files) - log1p(control_files)|
distance = days / 90 + (line_delta + file_delta) / ln(4)
line_ratio = (max(positive_lines,control_lines)+1) / (min(...)+1)
file_ratio = (max(positive_files,control_files)+1) / (min(...)+1)
```

Our 22 October independent re-evaluation of all 190 original selected C2 rows found **no disagreements** with their stored metrics (floating-point differences at approximately 1e-15). All pairs obeyed the 90-day and 4x changed-size calipers. Of 190 matches, 106 were Tier-A/exact, 9 Tier-A/superset and 75 Tier-B/exact.

## Verified distribution statistics

| Metric | Median | P90 | Maximum |
| --- | ---: | ---: | ---: |
| Absolute PR-time gap (days) | 6.65874421 | 36.07702315 | 61.79627315 |
| Changed-lines ratio (+1 adjustment) | 1.26128118 | 2.92803420 | 3.98433048 |
| Changed-files ratio (+1 adjustment) | 1.21980676 | 2.00000000 | 3.85714286 |
| Normalized distance | 0.53303631 | 1.33310297 | 2.45702204 |

The original C2 `SHA256SUMS.txt` provides immutable fingerprints for four input files (pairs, summary, balance and tier quality). An offline, fail-closed verifier and **17 synthetic-only regression tests** are committed as `analysis/frozen_c2_score_gate.py` and `tests/test_frozen_c2_score_gate.py`. GitHub CI never reads the Wits original records.

Run on approved, stable copies stored **outside** this repository:

```bash
python -m analysis.frozen_c2_score_gate \
  "/secure/local/C2_MATCHED_PAIRS_FROZEN.csv" \
  "/secure/local/C2_SUMMARY.json" \
  "/secure/local/C2_MATCHING_VARIABLE_BALANCE.csv" \
  "/secure/local/C2_MATCH_QUALITY_BY_TIER.csv"
python -m unittest tests.test_frozen_c2_score_gate -v
```

The full-file hash verification in this new command is independently executable but is **not claimed to have been run against all four Wits originals in this session**; the current selected-pair arithmetic was computed from read-only retrieved original C2 bytes and compared against the archived source metadata. No original cluster data was modified.

## Excluded scientific claims

This does not reproduce the full eligible-candidate graph, re-run the original maximum-cardinality / maximum-Tier-A / minimum-distance optimizer, attest the final August 29 SQLite or scanner baselines, establish vulnerability validity, or reproduce observational statistics and causal experiments. Preserve these as separate gates.
