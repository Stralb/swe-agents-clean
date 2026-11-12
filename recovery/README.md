# Research recovery — 10 November 2026

This branch preserves recovered materials for manual cleanup. The active miner, manuscript and analysis directories at the repository root were retained.

## Contents

- `github/arno-research-reproducibility/`: 52 files recovered from the private source repository, including historical CodeQL evaluators, audit tools, tests, reports and provenance.
- `cluster/research_artifacts/`: research scripts, experiment/evaluation drivers, extractors, database tools, configuration and Slurm jobs recovered from the Wits cluster.
- `cluster/miner/`: 223 source/configuration/launch files from the cluster miner checkout.
- `cluster/manifest.json`: original source paths and SHA-256 records. Credential-pattern matches were published only with redactions; original files remain on the cluster.
- `miner_comparison.csv`: comparison of cluster miner files with the original clean repository. Of 223 files, 80 had no same-path counterpart, 12 differed, and 131 matched. A missing same-path counterpart can reflect a renamed or reorganized file, so this is an intake comparison, not proof of missing functionality.

The cluster pass staged 3,878 files (84,205,575 bytes) and initially quarantined four others. A second check quarantined 31 staged files. The resulting recovery contains 3,847 unchanged code/configuration files, 35 redacted versions and the manifest. All 35 flagged files were retained in redacted form.

## Database backup

The working master is `ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite` (42,186,481,664 bytes; 127 tables at inspection). A separate evidence vault is `ARNO_EVIDENCE_VAULT_20261030.sqlite` (4,388,503,552 bytes). These are too large for ordinary Git blobs.

The approved destination is the private dataset [Stralb/malicious-issue-miner-data](https://huggingface.co/datasets/Stralb/malicious-issue-miner-data), under `backups/arno-master-20261110-v1/`.

Backup job 84244 creates separate SQLite Backup API snapshots, runs full SQLite integrity checks, records table counts and SHA-256 digests, compresses the snapshots, uploads them, and compares remote sizes and SHA-256 values. It never overwrites the working databases or older remote snapshots.

**At the time this note was written, backup was running. Upload success and integrity must be established from its final manifest; this note is not evidence of completion.** The cluster status file is `ARNO_MASTER_DB/snapshots/backup_20261110_v1/status.json`.

## Scope

This is source preservation, not a claim that the recovered code produced every historical result. Historical drivers may contain obsolete paths and assumptions. No historical scanner or experiment scripts were executed as part of the source recovery.

The code scan includes UTF-8 files with Python, shell, SQL, Slurm and common configuration extensions below the research directory and selected miner source directories. It skips symlinks, caches, dependencies, Git checkouts nested in the research tree, binary artifacts and individual files above 2 MB. It does not establish recovery of every earlier chat attachment or every external evidence reference in the databases.
