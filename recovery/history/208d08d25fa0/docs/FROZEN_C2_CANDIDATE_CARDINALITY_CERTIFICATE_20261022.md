# Frozen C2 candidate-count certificate — 22 October 2026

## Conditional matching-cardinality result

The complete original `C2_CANDIDATE_COUNTS_192.csv` was retrieved read-only, and the full 13,393-byte SHA-256 **matches** the archived `6e4e09e7ac4b091a018b9bb55cfeab581fb67196159a729cf034e8851b728c8d`. It records **192 positives**, **190 with one or more eligible controls**, and exactly **two without any**: cases `13918` and `17460`.

The original 190 frozen C2 pairs have **190 unique positive IDs**, **190 unique control IDs**, and every selected pair is eligible in its recorded tier according to that candidate-count table. Therefore, given these **source-recorded candidate counts**, a matching of 191 or 192 positives is impossible, and the frozen 190-pair matching is **maximum-cardinality**.

This is a formal *upper-bound certificate conditional on the frozen candidate counts*, not a new run of the original eligible-edge generator or global optimiser.

| Quantity | Source-verified value |
| --- | ---: |
| Positive cases | 192 |
| Positive cases with any eligible control | 190 |
| Positive cases with an eligible Tier-A control | 119 |
| Positive cases with an eligible Tier-B control | 189 |
| Tier A only / Tier B only / both / neither | 1 / 71 / 118 / 2 |
| Recorded Tier-A candidate edges | 1,098 |
| Recorded Tier-B candidate edges | 86,608 |
| Selected Tier-A / Tier-B matches | 115 / 75 |
| Source-recorded eligible but unmatched cases | 0 |

## Offline reproduction

```bash
python -m analysis.frozen_c2_candidate_cardinality \
  "/secure/local/C2_CANDIDATE_COUNTS_192.csv" \
  "/secure/local/C2_MATCHED_PAIRS_FROZEN.csv"
python -m unittest tests.test_frozen_c2_score_gate -v
```

The command independently hashes both original files, checks rows and source cohort, verifies each selected pair references a genuinely eligible tier in the **recorded** table, and proves the resulting cardinality bound. Normal GitHub CI uses synthetic data; no private candidate rows enter the repository.

A companion entrypoint in `analysis/frozen_c2_score_gate.py` independently replays selected-pair metrics, 90-day/4x calipers and all frozen summary/quality tables. The expanded synthetic suite contains **25 locally passing tests**, including seven candidate-certificate scenarios and one CLI rejection test.

## Still unverified

1. Regenerating **87,706 eligible candidate edges** and all 192 per-positive candidate counts directly from the hash-verified complete C1 source, including exact boundary and comparator semantics.
2. Whether **115 selected Tier-A matches** is the maximum possible after preserving 190 matched positives.
3. Whether selected controls have the minimum total normalised distance among all admissible assignments, and reconstruction of the original tie-breaking optimiser/seed.
4. Scanner validity, final August 29 SQLite authentication and published statistical results.

Keep the original Wits inputs immutable. The frozen C2 matching uses only pre-outcome matching variables and does not imply a causal security difference.
