# Source-only recovery intake — 20 October 2026

**Goal:** Preserve the original code and experiment history in the independent private repository. This is **not** a scientific-analysis stage, a new experiment, or the selection of a canonical implementation.

## Prepared source-only package

Package: `arno_code_history_source_only_20261020_v2.zip` (3,319,957 bytes). SHA-256: `fc63d5137ebbd4bab15fe42a748ed8f15cc0ec062d4cd62b65a25ea904dc94ec`.

The package is prepared locally and **has not yet been imported to the repository**. It contains 1,079 files: 1,075 historical source files plus four metadata records. All 1,075 indexed bytes/SHA-256 assertions pass. There are no duplicate member names, paths outside the stage, or symlink entries.

| Origin | Original regular members | Source files staged | Stage bytes |
| --- | ---: | ---: | ---: |
| Miner August 17 ZIP | 211 | 210 | 1,355,898 |
| Miner August 19 review-UI ZIP | 218 | 216 | 1,491,620 |
| Live miner TAR, including code backups | 5,427 | 518 | 8,377,798 |
| Discovery v2.1 implementation | 14 | 14 | 134,061 |
| Discovery v2.2 implementation | 10 | 10 | 74,494 |
| Decision-controls Step 7 collector | 5 | 3 | 17,101 |
| October job-driver archive | 601 | 104 | 475,499 |
| **Total** | **6,486** | **1,075** | **11,926,471** |

Of the 518 live-miner files staged, 242 are current-top-level source/config/documentation and 276 are backup code versions. Non-code backup JSON, Slurm logs, caches, raw evidence, database references and large runtime artifacts stay in the original archive. The compressed live archive remains separately identified by its SHA-256; the source-only package is not a substitute for it.

The source package preserves the original relative file path under an archive-specific `historical/` prefix. Importing it **does not** populate active `src/`, execute scripts, or certify their correctness. One original October Python driver (`owp14_20261018_v4/eval_668_uploaded_scannerfix.py`) fails syntax parsing and remains untouched as historical evidence; its corrected successor is separately preserved.

## Exclusions and privacy

Excluded: `.env.example`, `.streamlit/secrets.toml.example`, transient `.pytest_cache` files and a Python `.pyc` bytecode file. A conservative known-token signature check found no high-confidence credential signatures in the staged files; **this is not a comprehensive secret or licensing audit**. Original archives remain private. No bulk raw research data or third-party repository snapshots were included.

## Verification and import

The [read-only verifier](../tools/verify_source_snapshot.py) checks source file digests, path restrictions, index consistency and byte sizes:

```bash
python tools/verify_source_snapshot.py arno_code_history_source_only_20261020_v2.zip
```

Local verification result: `PASS` (1,075/1,075). The Windows import helper prepared for the researcher creates a **new GitHub branch** and refuses existing destination paths, never touching Wits. Merge is a separate human-reviewed action. It requires only Git and local access to the downloaded verified ZIP; it does not need SSH credentials or remote cluster commands.

## Release limitations

- Source snapshots ≠ complete data provenance. The 3,809-workflow database and full experimental outputs remain external.
- Some independent research-stage sources on Wits are not yet present in the seven selected archives.
- Active miner candidate selection, runtime environment reconstruction, security review, and regression testing remain future **reproducibility tasks**, not completed work.
- No scientific claims or historical result values were modified.

## Next engineering gate

1. Import the 1,075 files to a fresh private branch; verify file counts and hashes from the committed manifest.
2. Trace each archive-specific entrypoint and its dependencies without executing source that writes to existing paths.
3. Promote explicitly selected and tested modules into a clean active package, keeping historical versions intact.
4. Capture missing source archives and commit exact versioned code separately.


## Status addendum — 21 October 2026, after repository import

The line above describing the staging ZIP as **not yet imported** recorded
the original 20 October intake state. The separate private recovery Git branch
subsequently received all **1,075** originally indexed historical files, with
the frozen manifest and seven origin source groups retained. The source
consolidation work PR is based on that recovery branch and has not been merged
to `main`.

The [new repository-level verifier](../tools/verify_imported_sources.py)
compares **every committed imported path's original SHA-256 and byte count**
against the frozen index, plus checks the two independently attested CodeQL
phase-2 evaluators, with no historical source execution or writes. Treat a
green CI log as evidence of byte preservation **in this Git checkout**, not
as a guarantee the original seven archives, Wits data or 3,809-workflow
scientific outputs have been restored.
