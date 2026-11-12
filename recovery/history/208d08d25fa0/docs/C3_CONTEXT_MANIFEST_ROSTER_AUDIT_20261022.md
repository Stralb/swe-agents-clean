# Frozen C3 context-to-manifest reconciliation — 22 October 2026

**Result:** `PASS_C3_CONTEXT_SOURCE_SHA256_AND_BLIND_REPOSITORY_ROSTER_FINGERPRINT`.

The full **1,090,666-byte** original `C3_CONTEXT_RAW_190.csv` was independently retrieved from the approved **read-only** Wits research-artifact endpoint in 32 KiB ordered byte ranges. A streaming SHA-256 computation returned exactly the frozen digest `0224053cf034f97ff3ff5850bac1bfa18942c3c0f7de0431ed13832c0aff7bfb`. The quote-aware CSV stream contains **190 complete data records**, a **17-column header**, no malformed column-width records, and no open CSV field at end-of-file.

The context's `blind_id` and `repository` fields were independently compared with the frozen 190-row `C3_CONTROL_MANIFEST_BLINDED.csv`. Four order-insensitive checks agree: FNV-1a 64-bit sum and XOR of blinded IDs, and the same two checks for the paired `blind_id|repository` strings. All **190 manifest blind IDs** are distinct. The comparison disclosed no case-level IDs, original issue/PR text, or repository names.

This is a **strong aggregate roster consistency check**, not a formal collision-free proof of exact set equality: additive/XOR 64-bit fingerprints are not collision-resistant. The full source-file SHA-256 is separately exact and both frozen source identities are preserved. For an exact per-row multi-file join, run the existing `analysis.frozen_c3_blind_gate` on separately authorised originals outside Git; it also checks the issue, PR, context and implementation-filename populations.

Together with the preceding [full C3 source-byte audit](C3_FULL_SOURCE_BYTES_AUDIT_20261022.md), all three original large C3 CSVs are byte-authenticated. These files contain **blind evidence**, not the final annotation labels. The completed C4/C5 coding, C6 p-values and C7 pathway statistics remain unauthenticated and unreproduced, as do final August 29 SQLite bytes and historical scanner causality. The current read-only miner database query interface rejects nested final-snapshot filenames; no attempt was made to bypass its sandbox. No Wits source files or jobs were changed.

Machine-readable aggregate result: `provenance/c3_context_manifest_roster_audit_20261022.json`.
