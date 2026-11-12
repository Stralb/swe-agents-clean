# October 2026 CodeQL export part 08: intake audit

## Archive

Uploaded filename: `08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip`.

SHA-256: `be86fa352995a51bd4fa560a7532f721d66e5915fb47a8445ac88984309e0064`.

Despite its title, this particular export component contains **11 Base64 text chunks and a CSV part index**, not Python/Slurm execution scripts. The manifest checksums and byte sizes match all 11 chunks.

## Reconstruction (inspection only)

The six `owp14_20261018_transfer_v1` chunks concatenate to Base64 that decodes to a 51,838-byte ZIP with 12 `CASE_*_O.patch` entries. Decoded ZIP SHA-256: `a9b6965de4d246d1b7a6765e71ac50d3f578440d6678f53bedea4d1f84aaf85f`.

The five `owp14_w14_20261018_transfer_v1` chunks decode to a 32,040-byte ZIP with 14 `CASE_*_W.patch` entries. Decoded ZIP SHA-256: `6ca2054bd994bc50cc7228ce957b05fe221c16df02a032ac3c995998191440c9`.

The first bundle covers 12 cases; the second covers 14 (including W-only case patches for 08461 and 15151). The exported part index labels these source chunks `RAW_SOURCE_PRESERVED_NOT_REEVALUATED`.

**What this proves:** the source chunks can be recombined without corruption into specific historical patch ZIPs.

**What it does not prove:** compilation, successful patch application, CodeQL outcome, warning prevention, equivalence of prompts, functional success, or independence of generation.

## Security and publication treatment

Patch text may contain repository-specific code and problematic examples from security experiments. Retain original patch archives only in their secure historical storage; import reviewed source/test harness components separately. Do not commit the Base64 chunks as if they were runnable scripts.

## Missing evaluator lineage

The source package containing the actual October experiment drivers and their frozen configuration is still needed. Initial read-only inspection of `research_artifacts/prevention_pilot_phase2` found named evaluator scripts such as `evaluate_phase2.py` and `phase2_eval_v2.py`, together with functional evaluation scripts and multiple Slurm launchers. Their relationship to this specific O/W/P export is **not yet established**.

**Status:** two historical patch ZIPs reconstructed and verified, evaluator-script provenance open.
