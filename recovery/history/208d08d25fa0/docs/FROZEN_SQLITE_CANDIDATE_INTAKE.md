# Original miner SQLite — safe local candidate intake gate

**Current scientific status: BLOCKED.** The independent consolidation
repository does not contain an approved, complete, checksum-attested snapshot
of the SQLite database that produced the reported **3,809 GitHub workflows**,
**192 scanner-positive workflows**, **455 mapped producing changes in 191
workflows**, and the **342 C roots**. The 3,809/192/455 figures are *historical
reported outcomes*, not raw counts from an arbitrary miner `cases`,
`scanner_findings` or `scanner_runs` table. Their original SQL selection,
version/suppression policy, snapshot date and producing-change crosswalk are
still required. See P-002 and `docs/RESEARCH_MAP.md`.

## Why a new intake tool was necessary

The original `src.db.database.Database` class **must not** be instantiated in
normal writable mode against an original historical database: its
`apply_migrations()` mutates retrieval pagination and job state and can
delete obsolete job records. Even selecting `read_only=True` on the original
class would not verify whether the input is a complete, consistent frozen
snapshot or the correct dataset version.

The new **`analysis/frozen_sqlite_intake.py`** uses only Python stdlib
`sqlite3`, `hashlib` and a strict **separately private candidate manifest**.
It never imports the original miner Database class, sends SQL updates,
opens an archive, contacts GitHub/Wits, submits Slurm jobs, repairs tables,
or writes a report file.

## Prerequisites — not yet satisfied by the repository

A researcher must first provide **a legally permissible, consistent, fully
checkpointed or backed-up offline copy**, from the actual historical research
database. This is an independent source-recovery task; this document does
**not** authorize reading or copying an active Wits database or performing
any cluster operation. Simply copying a live SQLite main file while WAL is
active can omit committed work. Obtain the original source identity, snapshot
date/time, SQLite backup/checkpoint method, hash, and original query version
separately.

Keep the SQLite bytes and manifest **outside Git**, under a secure,
researcher-controlled local directory. Do not stage case texts, issue/PR
bodies, original database files, scanner logs or identification manifests in
this repository.

The **private manifest** must have the following structure, with actual
values provided from the approved staged snapshot; the dummy values below
are placeholders and intentionally cannot pass validation:

~~~json
{
  "schema_version": 1,
  "artifact_role": "historical_miner_sqlite_candidate",
  "source_identity": "UNVERIFIED_AS_ORIGINAL",
  "capture_method": "sqlite_backup_api",
  "sha256": "<64-hex-digest-of-the-approved-copy>",
  "bytes": 0
}
~~~

Allowed self-reported capture methods are `sqlite_backup_api`,
`sqlite_vacuum_into`, and `offline_checkpointed_copy`. This field is
**not independently authenticated by the tool**. The mandatory
`source_identity: UNVERIFIED_AS_ORIGINAL` makes clear that hash verification
of a user-provided manifest is not independent proof that the candidate
is the *original* study database.

## Verification — ordinary local terminal, never a Wits shell

From the cloned private repository, after a separate approved stable local
copy and private manifest have been prepared:

~~~bash
python -m analysis.frozen_sqlite_intake verify-candidate \
  "/absolute/private/local/frozen-miner.sqlite" \
  "/absolute/private/local/frozen-miner-manifest.json"
~~~

For a known large but stable database, integrity-check time can be increased
explicitly (up to 3,600 seconds):

~~~bash
python -m analysis.frozen_sqlite_intake verify-candidate \
  "/absolute/private/local/frozen-miner.sqlite" \
  "/absolute/private/local/frozen-miner-manifest.json" \
  --integrity-seconds 900
~~~

**Tool guarantees on passing input:**

- Rejects files missing from the disk, filesystem symlinks, noncanonical
  mutable sidecars (`-wal`, `-shm`, `-journal`), and any candidate whose
  bytes reside inside the private Git repository.
- Verifies the stored SHA-256 and byte length *before opening the database*,
  and checks source file identity/stability after inspection.
- Opens only the approved candidate through SQLite URI
  `mode=ro&immutable=1`, sets `PRAGMA query_only=ON` and
  `trusted_schema=OFF`, disables loadable extensions, and never calls the
  original Database constructor/migration methods.
- Requires a complete `PRAGMA integrity_check` returning exactly `ok`.
- Checks that the minimal historical miner tables and field names necessary
  for later miner analysis exist (schema variants may still need explicit
  version-specific schema handling).
- Emits only technical metadata, a SHA-256 fingerprint of the SQLite schema,
  and **unfiltered row counts** for an approved hardcoded set of tables;
  it never dumps raw issue/PR texts or arbitrary SQL query results.

**Output status:** `PASS_CANDIDATE_SQLITE_INTEGRITY_ONLY` and exit code 0
mean only that this **self-attested candidate** is byte-stable, readable,
technically compatible with a subset of the original miner schema, and
internally SQLite-consistent. The output explicitly preserves these flags:

~~~json
{
  "original_source_identity_independently_verified": false,
  "historical_cohort_inclusion_sql_verified": false,
  "reported_3809_workflows_reproduced": false,
  "reported_192_positive_workflows_reproduced": false,
  "reported_455_producing_changes_reproduced": false,
  "statistical_results_reproduced": false
}
~~~

An invalid, missing, changed, sidecar-dependent, uncheckable, non-SQLite or
schema-incompatible candidate returns exit code **2** and a blocking JSON
error. It is **never treated as an empty or clean research result**.

## Independently tested behavior

Run only the fixture tests on an ordinary machine:

~~~bash
python -m unittest tests.test_frozen_sqlite_intake -v
~~~

The fixture creates a brand-new tiny database from
`src.db.ephemeral.verified_schema_sql()`, never from Wits. The tests
exercise valid immutable reads, SHA/size changes, missing database, bad header,
wrong schema, symlink rejection, WAL/journal sidecars, self-promoted manifests,
CLI error codes and the invariant that **no real cohort counts are claimed**.

## Additional gates that must remain open

1. Obtain original research dataset export, source fingerprints,
   code/SQLite version, checkpoint provenance and the actual original
   inclusion/exclusion SQL for each reported figure.
2. Audit logical units: 3,809 issue→agent-associated PR *workflows* vs
   192 *scanner-positive workflows* vs 455 *producing changes* vs 342 *roots*.
   Multiple warnings, scanner retries, non-vulnerability CodeQL findings and
   overlapping cases cannot be collapsed by naive SQL COUNT(*).
3. Reproduce original scanner execution statuses and correct for known
   historical source behaviors: failed scans treated as already run,
   cross-scanner finding deletion, CodeQL malformed SARIF with zero results,
   and classification of CodeQL code-quality as vulnerability at case level.
4. Recreate the 455-to-342 root crosswalk against its original frozen files,
   adjudicate D/D7 without modifying them, and regenerate statistical
   tables with exact original filters and seeds.
5. Independently compare the O/W/P before/after CodeQL SARIF cases, using
   all 14 original missing baselines and original CodeQL 2.25.6 provenance.
   The modern genuine scanner smoke (CodeQL 2.27.3) is not historical parity.

**Source-of-truth boundary:** Until the original data plus SQL are
authenticated, this project can claim a tested *candidate SQLite intake
workflow*, **not** an independently reproduced empirical cohort.


## Source-expected discovery fingerprint found (source only)

The archived v1/v2/v2.2 discovery code contains a matching expected SQLite
SHA-256, **`126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`**,
and `deep_extract.py` contains the exact 3,809-case `cases` SELECT.
See [the source-only provenance record](FROZEN_DISCOVERY_DB_LINEAGE.md).
This does **not** mean the file was recovered: the actual SQLite content,
snapshot method and independent source identity remain absent. Use the
stricter `verify-discovery-snapshot` command when an approved SQLite
copy matching the source-embedded hash is available. `verify-candidate`
by itself cannot attest the historic database or research denominators.
