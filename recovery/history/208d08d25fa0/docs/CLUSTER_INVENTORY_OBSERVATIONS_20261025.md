# V6 read-only inventory checkpoint - 25 October 2026

The identified independent GitHub repository is `Stralb/arno-research-reproducibility`.
The original miner checkout is **not** the target for new code or data writes.
The V6 connector authenticated as `astrauss` to the Wits cluster and enumerated
original research artifacts in read-only mode. It did not execute jobs.

| Research input | Source-observed state | Proof or limitation |
| --- | --- | --- |
| Full discovery source DB | Path recorded in `full_corpus_deep_discovery_v2_20260829T181912Z/00_manifest/RUN_MANIFEST.json` | Expected SHA-256 `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`; no live rehash of final file this turn |
| Hugging Face dataset | `Stralb/malicious-issue-miner-data`, private, historical source-reported | No authenticated remote revision/ETag verified this turn |
| Root census inputs | `C_ROOT_CENSUS_FIX2_LATEST/final_selected/STEP2_EVIDENCE_AUDIT_455_NORMALIZED.csv`, 249,898 bytes | Directory and size observed, source is available for later hash-verified intake |
| Root census selection | `C_ROOT_CENSUS_FIX2_LATEST/C_SELECTION.json` | JSON says QC PASS and 455 producing changes in 191 cases; not re-audited from inputs |
| D-stage source evidence | `D_COMPLETE_ROOT_PROVENANCE_v1_0/D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz`, 11,020,359 bytes | Archive exists; must inspect exact members before reuse |
| D-stage codebook | `D_COMPLETE_ROOT_PROVENANCE_v1_0/00_FROZEN/D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md` | Present in read-only listing |
| D coder/final folders | `03_CODER_A`, `04_CODER_B`, `05_AGREEMENT`, `07_FINAL` | Empty according to V6 listing; absence there does not prove no copies elsewhere |
| Controls | `matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv`, 56,175 bytes | Frozen pair file exists and audit JSON says C2 opportunity-only selection passed |
| New70 | `new70_frozen_methodology_LATEST/NEW70_FULL_FROZEN_METHOD_ARCHIVE.zip`, 12,104,299 bytes | Archive exists; exact SHA not measured |
| Provenance | `PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv`, 1,936,940 bytes | File exists; later D/D7 corrections must not be replaced by Phase 6 |
| Historical O/W/P CodeQL baseline | 14 exact original before-SARIF files | Previously documented missing; none authenticated this turn |

This is a preliminary *location index*, not an authenticated full-corpus inventory.
File existence, source-named status and content authenticity are different.
A later authorized, bounded, read-only cluster inventory could hash only the
needed inputs, search other permitted locations for the missing D labels and
SARIF baselines, and output an append-only import manifest.

No Wits file/Slurm job was modified or submitted. No Hugging Face object was
uploaded, deleted or replaced. No GitHub repository was modified.
