# Verification of the imported 1,075 historical source files

The exact-byte sources were initially checked inside their source-only
staging ZIP by \`tools/verify_source_snapshot.py\`. After importing them
into Git, that ZIP-specific validation no longer guarantees that their
committed paths remain unchanged. The new
\`tools/verify_imported_sources.py\` closes this **repository integrity** gap.

Execute from the root of the independent private repository:

~~~bash
python -m tools.verify_imported_sources
python -m unittest tests.test_imported_source_integrity -v
~~~

The verifier uses only Python's standard library and reads every historical
path in the committed source index. It checks:

- Exactly **1,075** unique indexed files and **11,926,471** original bytes.
- The archived **SHA-256 and exact byte length of every individual file**,
  rather than relying on Git status or successful Python syntax compilation.
- The **seven archival source groups** and original archive digests/names
  against \`source_recovery_archive_summary_20261020.csv\` and
  \`source_recovery_package_status_20261020.json\`.
- Strict \`historical/\`-only canonical destination paths, original relative
  archive paths, absence of symlinks and no unexpected inserted files.
- The two separately recovered \`historical/codeql_phase2/*.py\` evaluator
  scripts, individually checked against their independent frozen file hashes
  in \`provenance/phase2_evaluator_sources.json\`. These scripts have
  documented filesystem side effects, and **are never run**.
- The sole unindexed historical file is the repository's
  \`historical/README.md\`, treated as documentation only.

The CI pipeline runs this verification after synthetic fixture tests and the
read-only O/W/P recorded arithmetic check. If an indexed historical source is
modified or missing, the job fails. The source history is not reformatted,
converted, rewritten or auto-repaired. The script emits only a JSON summary
to standard output; it does not export private source text.

### Research-boundary interpretation

A successful integrity gate proves byte preservation of the specific original
source files **within the independent repository**. It does **not** establish
that all research scripts were recovered, that they are safe or executable,
that the chosen source versions generated the published tables, or that
the original dataset is present. The original Git/cluster source archives
remain independent provenance objects that require separately kept SHA-256
checksums. It is not a scanner-quality, statistical or causal-validation step.

No Wits access, Slurm job, external repository modification or local
historical file write is performed.
