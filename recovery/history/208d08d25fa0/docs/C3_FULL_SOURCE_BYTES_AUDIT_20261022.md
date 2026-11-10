# C3 complete issue/PR/context source-byte authentication — 22 October 2026

**Result:** `PASS_C3_THREE_LARGE_CSV_FULL_SOURCE_SHA256_AND_190_LOGICAL_ROWS`

This closes the earlier partial-file-integrity gap for the **three large original C3 evidence CSVs**. Files were read from Wits `matched_control_c3_v1_0` through an approved **read-only** interface. All bytes were retrieved in order and hashed independently against the archive's SHA-256 manifest; source files and cluster jobs were untouched.

| Frozen source | Original bytes | SHA-256 match | Record count |
| --- | ---: | :---: | ---: |
| `01_ISSUE_BLIND/C3_ISSUE_BLIND_190.csv` | 534,907 | YES | 190 |
| `02_PR_BLIND/C3_PR_BLIND_190.csv` | 577,084 | YES | 190 |
| `04_CONTEXT_SEPARATE/C3_CONTEXT_RAW_190.csv` | 1,090,666 | YES | 190 |
| **Total** | **2,202,657** | **3/3** | — |

Full SHA-256 values and the exact original relative paths are in `provenance/c3_full_csv_byte_audit_20261022.json`. The first file was fully CSV-parsed: exactly **190 unique blind IDs**, **122 distinct repositories**, no malformed width records. The PR and context sources were scanned for quote-aware **logical CSV row termination**, each producing 191 logical lines including the header, with closed quotation state at EOF. Because the source hashes match the archived values, these are byte-identical to the original frozen exports. The PR/context pass did *not* independently reparse all field-level crosswalks or verify every record against the manifest.

## How this extends the prior audit

The earlier independently verified **five small C3 sources** are the locked C2↔C3 mapping, control manifest and three blank annotation templates. Their 190-record membership check had **zero mismatches**. The current audit authenticates the larger issue, PR and context text exports, not merely archived QC reports. Together they establish full-byte identity for the eight original C3 CSV input/metadata artifacts. The original `analysis/frozen_c3_blind_gate.py` remains the appropriate **fully joined** local replay when all approved originals and 190 implementation-packet names are staged together.

## Limits that must not be obscured

1. No field-level C3 issue+PR+context rejoin against the locked manifest was performed in this multi-part checksum pass; do not claim this more demanding offline gate was run.
2. The **190 implementation text packet contents** have not been SHA-authenticated.
3. The C3 **annotation templates remain blank**. Completed semantic coding exists in later *C4/C5* artifacts that were cataloged in the Library, but their raw bytes are not presently materializable.
4. Thus the nine C6 matched primary p-values, Tier-A sensitivity and C7 pathway stratifications are **source-reported, not independently re-calculated**.
5. This does not authenticate the final August 29 SQLite, original scanner versions/rulepacks/finding introduction, 14 missing October O/W/P baseline SARIFs, the global C2 matching optimiser, or any causal counterfactual result.

No private source text, control/positive mapping, author, repository-level record, or raw CSV has been included in Git history.
