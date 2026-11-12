# 23 October 2026 — AServerV6 live Wits reconnection and C2 original-byte authentication

**Status:** `PASS_C2_FULL_SHA256_USING_ASERVER_V6__C1_FRESH_SHA_AND_FINAL_SQLITE_STILL_OPEN`.

## Read-only connection facts

The new `mcp__AserverV6__` connector reached Wits SSH port 22 and authenticated as `astrauss`. It confirmed the permitted research root `/home-mscluster/astrauss/research_artifacts` exists and enumerated the restricted historical miner database directory `/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data`. All checks were read-only; no cluster source files, jobs or scripts were changed. This note describes V6, not the older V4/DCR connection.

The supported `query_miner_database` endpoint rejects `final-study-snapshot-20260829/full3809-scanner-complete-20260829.db` as a subdirectory path, with the explicit result: `Database must be a filename within the fixed miner data directory`. The original final 29 August DB did not appear in `list_miner_databases` (which enumerates top-level historical filenames only). No alternative file path was guessed, and the original final DB hash remains **unverified** through V6.

## Original C2 frozen CSV independently authenticated in full through V6

Original source: `matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv`.

- Retrieved exactly **56,175 bytes**, via two disjoint 32-KiB-capped read-only `read_artifact_chunk` calls. Chunk offsets and total byte size agreed.
- Reassembled the raw binary bytes locally in the tool's transient execution and computed SHA-256 from the complete byte sequence, rather than comparing only JSON counts or individual chunk digests.
- Tested the SHA-256 implementation on the standard `abc` known-answer vector (`ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`) before trusting the observed digest.
- **New complete-file SHA-256:** `4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b`.
- This is an **exact match** to the previously frozen source-expected C2 checksum. Thus the original C2 file bytes now have a **fresh independent verification through AServerV6**.

This authentication confirms C2 source identity; the separate prior C1–C2 case-level crosswalk tested 3,809 C1 rows, 190 original pairs, and 380 matched records without field mismatch. The present full-byte checksum step does **not** independently rehash C1 or rerun C6 significance calculations.

## Remaining connection and source limitations

A fresh full-file C1 SHA-256 could not be completed in this V6 attempt: at least one C1 32-KiB read returned a Wits SSH port-22 timeout, and an attempted larger batched read was blocked by tool-level safety checks. Other C1 chunks did return successfully, but they are insufficient to claim full SHA authentication **in this attempt**. Earlier source-expected C1 checksum: `6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b`.

The original frozen final SQLite remains out of reach of V6's restricted filename-only database query action and has not had its expected SHA-256 `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa` freshly calculated from its original bytes.

The original C6 paired master/positive semantic labels, 43 D/D7 classification disagreements, and 14 historic O/W/P before-SARIF files remain unresolved. Do not treat a healthy SSH check, successful C2 verification, or indexed C6 marginal recalculation as clearing these separate source authentication and scientific release gates.

**No historical research data was mutated, no Slurm jobs were submitted and no study labels were changed.**
