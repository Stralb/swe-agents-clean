# Historical Source Preservation

This folder will preserve **references and reviewed snapshots** of all source generations and failed/superseded implementations. The live miner archive contains **5,106 individual backup-file members** under `backups/`; every such file is held in the original 47 MB hash-registered source TAR, not deleted or assumed correct.

No bulk backup code is imported into active `src/` yet. To promote a historical file, record its precise archive hash, member path, file digest, reason for selection, competing versions, meaningful tests and research provenance. A rejected or buggy implementation remains referenced in the history ledger; it is not silently erased.

See `../provenance/artifact_register.csv` and `../provenance/active_source_index.csv`.

## Recovered three-case CodeQL baseline evaluators

The `codeql_phase2/` subdirectory contains the exact historical source files `evaluate_phase2.py` and `phase2_eval_v2.py` downloaded from Wits. They are **unsafe to execute on the cluster** because they contain `shutil.rmtree`, archive extraction and other write/replace operations. Do not import them in active code or execute them in CI. Their file hashes and known problems are documented in `provenance/phase2_evaluator_sources.json` and `docs/PHASE2_EVALUATOR_AUDIT_20261020.md`. These files cover three O-only cases, **not** the later O/W/P evaluation.
