# Frozen C1 scanner-opportunity CSV — standalone local verification gate

**Source-reported original input:** `matched_control_c1_v1_1/C1_CASE_SCANNER_OPPORTUNITY_3809.csv`, size **841,710 bytes**, expected SHA-256:

`6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b`

The Wits C1 manifest reports **3,809 unique cases, 192 positive labels and 3,617 potential negatives**. Its 192-positive set is **not** equivalent to the intermediate miner `needs_review` statuses (138 in the August 17 snapshot and 198 in the later continuation snapshot). The original C1 CSV **has now passed full-file independent SHA-256 and stored-row/label verification** through the approved read-only cluster artifact reader. It contains 3,809 strictly increasing, unique case IDs with 192 recorded positives and 3,617 recorded negatives. This **does not** establish that the stored labels can be regenerated from the final SQLite database or that every scanner result is correct.

The new `analysis/frozen_c1_cohort_gate.py` independently checks a private, **offline** copy of that exact CSV, without requiring C2:

```bash
python -m analysis.frozen_c1_cohort_gate "/secure/local/C1_CASE_SCANNER_OPPORTUNITY_3809.csv"
python -m unittest tests.test_frozen_c1_cohort_gate -v
```

It requires exact SHA-256 and byte length, a unique decimal `case_id` on each row, a parseable PR ID and nonblank repository, binary `is_positive` values, nonempty/unambiguous scanner-opportunity signatures for positive rows, and precisely the recorded **3,809 / 192 / 3,617** partition. It refuses symbolic links, paths inside Git, missing or altered bytes, and malformed rows. Output contains only aggregate counts. A violation exits **2**; nothing is repaired or written.

**Important:** Successfully replaying C1's original frozen `is_positive` column establishes only that the same **stored labels** have been recovered. It is **not** independent evidence the labels are scientifically correct, scanner-positive vulnerabilities are validated, or the original 192 labels can be reconstructed from the SHA-matched final SQLite using its frozen scanner-opportunity policy. For that, the final dataset, archived C1 transformation code, tool versions and scanner-run provenance are separate gates.

The normal GitHub CI uses only a synthetic 3-row fixture and never downloads or uploads the private original C1 CSV.

## Verified independent read-only file audit — 21 October 2026

The complete 841,710-byte file was read using 26 ordered, contiguous byte-range chunks. SHA-256 of the exact concatenated original content matched the frozen C1 hash above. The case-ID order was strictly ascending across both byte-range halves, establishing unique numeric IDs, and no `is_positive` field was outside 0/1. Aggregates: **3,809 rows = 192 stored positives + 3,617 stored negatives**. See `provenance/c1_cohort_readonly_audit_20261021.json`. No private CSV bytes, case-level labels or GitHub source texts were committed. The local-only verifier is available for independent later replay. C1–C2 cross-file membership and original-positive recomputation from final scanner runs remain separate verification gates.
