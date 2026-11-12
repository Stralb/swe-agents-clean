# D evidence export v1.1: independent intake audit (2026-10-20)

## Input and identity

- Source filename: `D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz`
- SHA-256 (uploaded compressed archive): `251f4c4f4fd7b3ba84e82d2c20e7af681322bf87e241ba793b006e2169db2b18`
- Archive: 15 regular files, six directories, 51,498,528 uncompressed regular-file bytes.
- All 14 internal SHA-256 manifest entries match the archived regular-file contents.

## Independently checked accounting

- Pass A evidence JSONL: 342 distinct evidence packets.
- Pass B blinded evidence JSONL: 342 evidence packets.
- Private alias crosswalk: 342 entries as reported in source QC.
- C5 producing-change mapping: 455 rows.
- C6 root census: 342 rows.
- D evidence index: 342 rows.
- Historical cases/workflows: 191, as stated in source QC.

These are **evidence-packet** counts, not counts of independently reproduced semantic labels.

## Source-reported completeness

| Channel | Status and counts |
| --- | --- |
| Issue / pre-introduction human evidence | COMPLETE: 342 |
| True-base target context | COMPLETE: 342 |
| Bounded repository search | COMPLETE: 342 |
| Project instructions | COMPLETE: 226; NOT_APPLICABLE: 116 |
| Dependency/toolchain | COMPLETE: 342 |
| External guidance | NOT_APPLICABLE: 208; URLS_PRESENT_UNFETCHED: 134 |
| Chronology | COMPLETE: 301; INCOMPLETE: 41 |

Both archived build and independent audits report PASS, and the archived identity/semantic leakage checks report zero detected hits. Those checks do **not** establish absence of every kind of information leakage.

## Scope of the package

The exported README expressly states that this deterministic export **does not perform semantic classification** and does not label H/T/M/U or T1–T5. It includes full issue/context evidence, potentially identifying repository/case data, and a **private Pass B crosswalk**. Do **not** commit raw evidence, that crosswalk, or the original archive to the shared code tree. The upload itself is retained outside Git.

## D-final versus D7: what this does and does not settle

The later `D_FINAL_COMPLETE_ROOT_PROVENANCE_v1.0` package reports M=234, H=5, T=103; a distinct D7 bundle reports M=233, H=6, T=103. Our existing ledger records 43 differing root explanation-tier entries, including one H/M reroute (`CROOT-00649-01`). The new pre-coding evidence export cannot choose the authoritative semantic label.

Of those 43 disputed roots, all 43 have chronology marked COMPLETE **in this evidence index**; 18 show `URLS_PRESENT_UNFETCHED` in the external-guidance channel. The case `CROOT-00649-01` also has `URLS_PRESENT_UNFETCHED` despite complete chronology. Do not infer that this causes the reroute without consulting the later adjudication and correction history.

## Follow-up

1. Trace each disputed label to the D4 adjudication decision, any later re-audit, and source-document chronology.
2. Apply the frozen T5 completeness rule: a genuinely material unfetched URL cannot establish a complete evidence search.
3. Leave the existing two frozen semantic result archives unmodified until row-level adjudication has been reconstructed.

**Status:** archive-integrity checked; scientific disagreement unresolved.
