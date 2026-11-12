# C1 ↔ C2: full frozen cross-file membership reconciliation

**Audit date:** 22 October 2026  
**Result:** `PASS_STORED_C1_C2_CROSSFILE_MEMBERSHIP_ONLY`

The archived C1 scanner-opportunity case table and C2 matched-control table are now **fully reconciled at the recorded-data level**. All comparisons were performed through the approved read-only Wits artifact interface. The original files, Wits databases and earlier audit ledgers were not modified. The detailed aggregate-only result is `provenance/c1_c2_crossfile_readonly_audit_20261022.json`.

## Source identities

| Frozen artifact | Bytes | Previous independent SHA-256 |
| --- | ---: | --- |
| `matched_control_c1_v1_1/C1_CASE_SCANNER_OPPORTUNITY_3809.csv` | 841,710 | `6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b` |
| `matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv` | 56,175 | `4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b` |

Both SHA-256 values were independently verified during the 21 October file-level audits. This cross-file pass **did not rerun full-file SHA-256**; it consumed read-only original CSV byte ranges and compared their member records.

## Checked membership and matching invariants

| Recorded-data check | Independently observed |
| --- | ---: |
| Total C1 rows accounted for | **3,809 / 3,809** |
| C1 stored positive labels | **192** |
| C1 stored negative labels | **3,617** |
| C2 positive members matching C1 | **190 / 190** |
| C2 negative-control members matching C1 | **190 / 190** |
| Tier A same-repository pairs | **115 / 115** |
| Tier B cross-repository exact-opportunity pairs | **75 / 75** |
| C1↔C2 outcome label, repository, or opportunity discrepancies | **0** |
| C2 reuse, self-match, opportunity-tier, or 90-day-caliper violations | **0** |
| Unmatched positives | **2** — case IDs `13918`, `17460` |

The inspection proceeded over three contiguous windows. They contributed 902, 2,515, and 391 complete row records. One **negative** record, crossing the 753,664-byte window boundary (byte range 753,522–753,748), was reconstructed separately to avoid dropping a split CSV line: **902 + 2,515 + 391 + 1 = 3,809**. Positive counts across those windows were 27 + 133 + 32 = **192**. Matched-member counts were 60 + 267 + 53 = **380**. No mismatched C1/C2 member record was observed.

## Reproduction procedure on separately approved local copies

The repository already contains the independent, fail-closed offline verifier. No additional alternate matcher or case-label rules were created:

```bash
python -m analysis.cluster_stage_lineage verify-staged-c1-c2 \
  "/secure/local/C1_CASE_SCANNER_OPPORTUNITY_3809.csv" \
  "/secure/local/C2_MATCHED_PAIRS_FROZEN.csv"
```

This command checks the full frozen file digests and member-level constraints, printing aggregates only. **Normal GitHub CI uses synthetic fixtures**, not the Wits original CSVs.

## Scientific limits and next gate

**Validated:** the stored C1 and C2 records are mutually consistent and the frozen matching pairs obey the checked constraints.

**Not validated by this pass:** the original C1 outcome-derivation SQL, historical scanner validity, rerunning the deterministic matching optimiser, the August 29 final SQLite database's current SHA-256, 455 producing changes, 342 roots, downstream matched statistical claims, or intervention effects.

The next blocker is authenticating the immutable final SQLite snapshot against the source-declared digest `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`. No older `needs_review` status counts should substitute for the frozen 192-positive label population.
