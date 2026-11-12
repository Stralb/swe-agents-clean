# Recovery of original ChatGPT research artifacts (25 October 2026)

**Scope:** historical original research materials, not a plan to rerun the experiment. See `chatgpt_library_security_artifacts_20261025.csv` for the per-file inventory.

- Indexed 470 **candidate library entries** across 11 filtered listing pages, with filenames, sizes, created dates and source paths. Categorization is based on filenames and must be independently validated.
- Status **LISTED_ONLY_NOT_BYTES_VERIFIED** means Library confirms the item exists, but its raw bytes are not presently materializable through the active Project file interface. Do not call it imported; no SHA-256 was computed.
- Repeated suffixes `(1)`, `(2)`, or `(3)` may be backups, genuinely distinct artifacts, or naming collisions. Never deduplicate on filename or byte size alone. Compare hashes after upload.
- Historical frozen labels/coding results must remain append-only; keep blind-versus-unblinded packets separate. Do not recreate missing labels or rerun model generations.

## Immediate upload batches (originals from Library or historical chats)

### Batch A: full previous handoffs and adjudicated evidence
- `ARNO_RESEARCH_ESSENTIAL_SOURCES_2026-08-20.zip` (89427300 bytes, Library listed)
- `agent_security_research_recovery_2026-10-20.zip` (47548007 bytes, Library listed)
- `ARNO_EVIDENCE_20261022_212644.zip` (3661280 bytes, Library listed)
- `ARNO_HUMAN_REVIEW_EVIDENCE_VERIFIED_v2.zip` (3765241 bytes, Library listed)
- `ARNO_PATCH_EVIDENCE_RECOVERY_v1.zip` (236998 bytes, Library listed)
- `D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz` (11020359 bytes, Library listed)
- `D_FINAL_COMPLETE_ROOT_PROVENANCE_v1.0.tar.gz` (185033 bytes, Library listed)
- `D7_DISCOVERY_HOLDOUT_BUNDLE_GPT56SOL_v1.0.tar.gz` (72223 bytes, Library listed)

### Batch B: frozen matched/control, provenance, and phase7 files
- `C6_MATCHED_POSITIVE_VS_CONTROL_v1.0.tar.gz` (117528 bytes, Library listed)
- `C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz` (106359 bytes, Library listed)
- `PROVENANCE_SCALEOUT_Phase6_FINAL_v1.0.zip` (1299243 bytes, Library listed)
- `PROVENANCE_Phase7_Validation_FINAL_v1.0.zip` (500343 bytes, Library listed)

### Batch C: original T1/T2 experiments and S5PAIR generation
- `T1_V9_FULL_BLIND_REVIEW.tar.gz` (711834 bytes, Library listed)
- `T1_V9_BLIND_ADJUDICATION_FROZEN_v1.tar.gz` (5130 bytes, Library listed)
- `T1_PRIMARY_PILOT_RUN_BUNDLES_v1.tar.gz` (52968 bytes, Library listed)
- `T1_REAL_EXPERIMENT_5_CHAT_BUNDLES.zip` (91745 bytes, Library listed)
- `T2_FINAL4_RUNS_v1.zip` (1593754 bytes, Library listed)
- `S5PAIR001_12_CHAT_INPUTS.zip` (60290353 bytes, Library listed)
- `S5PAIR001_PILOT_AUDIT_BUNDLE_v1.zip` (76684 bytes, Library listed)
- Also the original `G001_OUTPUT.zip` through `G012_OUTPUT.zip` (each separate) and the associated `G001_INPUT.zip` through `G012_INPUT.zip` if not covered by the intact umbrella archive. Verify role and all variant aliases by SHA-256.

### Batch D: generated code and evaluation trail
- `02_ALL_GENERATED_PATCHES.zip` (1897370 bytes, Library listed)
- `03_CODEQL_SARIF_AND_SCANS.zip` (7513750 bytes, Library listed)
- `04_FUNCTIONAL_TESTS_AND_TRIAGE.zip` (357391 bytes, Library listed)
- `07_AGENT_PROMPTS_AND_TRACES.zip` (423491 bytes, Library listed)
- `08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip` (87730 bytes, Library listed)

### Batch E: old frozen NEW70 and 122 case classifications
- `NEW70_90_LOCKED_FOR_LATER.zip` (9111494 bytes, Library listed)
- `NEW70_Phase9_Risk_Assessment_FINAL_v1.0.zip` (135249 bytes, Library listed)
- `F1-F5_Blind_Real122_Audit_v1.0.xlsx` (97216 bytes, Library listed)

## Recovery/ingestion rules
1. Copy only the **original attachment bytes** to an isolated staging area. Keep the original filename; store raw SHA-256 and byte count.
2. List archive members and check for encrypted member, symlink/hardlink, Zip Slip path traversal, and duplicate member names; do not execute original scripts or trust manifests without comparison.
3. Record provenance: ChatGPT Library path, historical chat name/date where known, source archive hash, nested path, experiment unit IDs and the first script/model version used.
4. Import original raw prompts, completions, generated patches, log outputs, SARIF, CSV labels, revisions and failed runs as separate immutable evidence; don't collapse alternative versions.
5. Keep secret/unblinded condition maps separated from blind review. Never treat scanner findings as confirmed vulnerabilities. Resolve D-original vs D7 route discrepancies through documented adjudication only.
6. Audit missing expected files and classify each as `not_found`, `listed_only`, `source_bytes_verified`, `ingested`, `crosswalk_verified` (mutually distinct states).

## Technical limitations
- GitHub repository: `Stralb/arno-research-reproducibility`; this index records no private data bytes.
- Original Wits research directories and original miner SQLite: read-only. Hugging Face private data is incomplete and is not a source of truth until source hashes and revisions are confirmed.
- The ChatGPT Library entries are currently metadata-accessible, but raw materialization into this Project's working container is unavailable. The author should attach selected original ZIP/tar.gz files from Library/old chats in batches.
