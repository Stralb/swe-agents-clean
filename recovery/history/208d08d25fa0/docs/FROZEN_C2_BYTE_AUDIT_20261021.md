# Frozen C2 pair artifact — direct read-only evidence (21 October 2026)

The original `matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv` was read from the Wits research-artifact store through approved **read-only** tools, and its complete **56,175 bytes** matched the pre-established source SHA-256:

`4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b`

The resulting CSV rows showed **190 unique positives and 190 unique controls**, with **115 Tier A same-repository** pairs and **75 Tier B cross-repository** pairs. Tier A matched same-repo/opportunity-superset; Tier B matched different-repo/exact-opportunity; no violations of the 90-day time caliper were observed. **No private case-level rows have been added to Git.** Metadata is recorded in `provenance/c2_pair_readonly_audit_20261021.json`.

## Independent local replay without the unverified C1 CSV

A new standalone gate runs against a separately approved local copy outside the repository:

```bash
python -m analysis.frozen_c2_pair_gate "/secure/local/C2_MATCHED_PAIRS_FROZEN.csv"
python -m unittest tests.test_frozen_c2_pair_gate -v
```

It requires the frozen **exact SHA-256 and byte length**, unique positive/control identifiers, no self-match, correct per-pair repository labels and scanner-opportunity relations, correct 115/75 tier split, and finite time differences in the original 90-day caliper. It deliberately prints **only aggregate counts**. Failures return exit code **2**. The normal repository CI tests the logic using disposable synthetic CSVs; it cannot access the original private cluster CSV.

## What this does not establish

- The **3,809 C1 case labels or the 192 C1 positives** are not verified merely by reading the 190 frozen C2 pairs; the complete C1 CSV still requires a SHA-matched, locally approved copy.
- C2 exact pair-membership integrity **does not reproduce the original matching optimizer**, candidate selection, or all C1 scanner success and exclusion rules.
- The final August 29 SQLite database, its authenticated Hugging Face revision and SHA, original CodeQL SARIF, producing-change root annotation and causal experiments are separately blocked.

This artifact is evidence of a **specific recovered frozen input's bytes and pair structure**, not a claim that the research intervention reduces security regressions.
