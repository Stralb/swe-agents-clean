# Reproduction notes

## What is included

- `data/matched_aggregates.json`: paired category matrices, discordant binary counts, and source-reported delay results.
- `data/cohort_lineage.json`: source-recorded cohort and matching totals.
- `data/pathway_aggregates.json` and `data/bootstrap_reference.json`: indexed checks and sensitivity references.
- `src/` and `scripts/`: the recovered miner implementation.
- `analysis/`: offline checks for recorded counts and separately supplied original files.
- `dataset/`: documentation, schema and build scripts for the study dataset.
- `experiments/rq3/`: the cluster scripts behind the RQ3 replay comparison, copied verbatim with SHA-256 provenance. They are tied to the cluster directory layout and are not run by `make check`.

The miner was imported from a recovered 20 October 2026 source candidate, and the initial import was checked against the source file hashes. Later changes reorganized paths, imports, commands, tests, and documentation without rewriting the collection or scanner algorithms. It is not independently established that these exact source bytes produced every historical scanner result. The original frozen SQLite database, scanner outputs, query packs, and runtime environment are not included in this repository. Case-level data, including annotations, are released separately as the study dataset (see `dataset/README.md`).

## Offline checks

```bash
make check
```

This runs syntax validation, recalculates eight paired tests from the bundled aggregate tables, checks the recorded cohort arithmetic, and executes a selected set of unit tests. The ninth paired test is checked against its historical reported p-value, not recalculated from the aggregate file.

The individual commands are:

```bash
python3 -m analysis.matched_results --check
python3 -m analysis.cohort_lineage audit-recorded
python3 -m unittest discover -s tests -p 'test_matched_results.py' -v
```

The cohort command checks the consistency of recorded totals. It does not read the original database or rerun the original cohort-selection process.

With an authorized copy of the original 190-pair CSV staged outside the repository, run:

```bash
python3 -m analysis.pair_level_replay --original-pair-master /path/to/C6_MATCHED_PAIR_MASTER_190.csv
```

The program checks the file shape and size and recalculates the nine paired tests. Its newly computed hash is not an authenticated match to the original without a trusted independent source digest.

For the original cohort and matching CSVs, use `python3 -m analysis.cohort_lineage verify-staged-c1-c2` with the two required local paths. The existing matcher can be audited, but the optimizer that selected those matches and the scanner runs that produced the labels are not reconstructed here.

## Known limits

The original miner has two scanner-applicability errors. One helper counts `artifact_profile` metadata as a scanner route. Another treats a missing `ci_security` route as applicable. The tests record these as expected failures. The collection logic is preserved for historical comparison; future collection should correct the functions and evaluate the effect on inclusion.

The distributed cluster runtime used to run the miner at scale is not included. The dependency requirements are not an exact historical lockfile.

Four tests outside `make check` fail on the current code: `test_codeql_force_rescan.py::test_non_codeql_job_does_not_force_rescan`, the two tests in `test_live_stagnation_fixes.py`, and `test_ui_status_refresh.py::test_direct_full_scan_syncs_jobs_and_marks_clean`. They concern scanner-job status bookkeeping in the miner and are left unchanged so that the collection logic matches the historical code.

Collection, scanning, and database initialization can write data. Run them only against an isolated database. None of the offline analysis commands above require a GitHub token or execute scanners.

The full historical working archive, including experiment drivers, intermediate outputs and earlier code revisions, is kept privately and is available on request.
