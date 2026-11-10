# Reproduction notes

## What is included

- `data/matched_aggregates.json`: paired category matrices, discordant binary counts, and source-reported delay results.
- `data/cohort_lineage.json`: source-recorded cohort and matching totals.
- `data/pathway_aggregates.json` and `data/bootstrap_reference.json`: indexed checks and sensitivity references.
- `src/`, `scripts/`, and `ui/`: the recovered miner and inspection implementation.
- `analysis/`: offline checks for recorded counts and separately supplied original files.

The miner was imported from `Stralb/arno-research-reproducibility`, commit `865b40e9bef4e552cefb6217c10aedb53cb6e8a7`, which contains a recovered 20 October 2026 source candidate. The initial import was checked against the source file hashes. Later changes reorganized paths, imports, commands, tests, and documentation without rewriting the collection or scanner algorithms. It is not independently established that these exact source bytes produced every historical scanner result. The original frozen SQLite database, row-level annotations, scanner outputs, query packs, and runtime environment are not included.

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

The distributed runtime also contains cluster-specific assumptions and references to Slurm launch files that are not included in this release. Local syntax checks do not establish that the cluster runtime works in a new environment. The dependency requirements are not an exact historical lockfile.

Collection, scanning, and database initialization can write data. Run them only against an isolated database. None of the offline analysis commands above require a GitHub token or execute scanners.

The materials under `literature/` are earlier coursework and research notes. They are not the manuscript reporting these results.
