# Archived discovery SQLite identity and 3,809-case linkage

## Newly recovered, source-declared fingerprint

Three historical discovery source versions hard-code the **same expected
SQLite SHA-256**:

`126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`

Their recorded unit is **3,809 case linkages**. This is an expectation
embedded in source, **not** a calculated checksum of recovered SQLite bytes
and **not** the scanner-positive cohort definition.

| Frozen archived source | Original file SHA-256 | Embedded claim |
| --- | --- | --- |
| `analysis/full_corpus_discovery_v1_1/discovery.py` | `d6b980ff758b548226c8a6b2099963fafdc02f093fe63fc2b09fc6a0b02e0ca2` | 3,809 cases; expected DB SHA |
| `analysis/full_corpus_deep_discovery_v2/deep_common.py` | `ec9d4b7910403d9c1fc37e8954c4f1c929185dcc5a7cb26a3085166f73a88896` | 3,809 cases; expected DB SHA |
| `v22_common.py` (separate discovery v2.2 archive) | `9d0f6e93633543b60a46a4cd1adf40162af0415c44dd542a5377958b70774e27` | 3,809 cases; expected DB SHA |
| `v21_common.py` (separate discovery v2.1 archive) | `d9494f9b760d9024c9be9c46f8b3cb9247290aae9be8714dcbb7c00d15bca475` | 3,809 cases; no SHA constant |
| `deep_extract.py` (live miner archived v2 source) | `699e8d597bb9940e261160904adb19f020bec0442f1dfe2e1b8805d8a1f307f7` | Exact case SQL and uniqueness check |

These are **related source versions**, not three independent database
copies. The new tool hashes all five original code files and parses them
with Python `ast` **without importing or executing historical code**.

## The actual fixed discovery case query

The archived `deep_extract.py` uses `safe_read_sql` with
`table="cases"` and this SQL:

~~~sql
SELECT id AS case_id, repo_id, issue_id, pr_id FROM cases ORDER BY id
~~~

It requires **3,809 rows with 3,809 unique case IDs**. Case-linkage
membership is a different unit from scanner findings or root decisions.
This source SQL is not evidence that the exact issue→merged-agent-PR
*security-paper inclusion and exclusion logic* has been recovered.

## What is executable now (no database)

Run from the private Git checkout in an ordinary local terminal:

~~~bash
python -m analysis.discovery_database_source_lineage audit-source
python -m unittest tests.test_discovery_database_source_lineage -v
~~~

The static source auditor reports `ARCHIVED_ANALYSIS_FINGERPRINT_SOURCE_VERIFIED`
after checking three embedded hashes, five exact original source file
checksums and the unique fixed SELECT. It explicitly reports
`original_3809_case_linkage_rows_reexecuted=false` because the
**actual database snapshot is still missing**.

## Later: only if the exact historical SQLite is safely recovered

A separate, approved, complete SQLite snapshot may be staged privately
outside Git along with a candidate manifest as described in
`docs/FROZEN_SQLITE_CANDIDATE_INTAKE.md`. Then run:

~~~bash
python -m analysis.discovery_database_source_lineage verify-discovery-snapshot \
  "/absolute/private/local/frozen-miner.sqlite" \
  "/absolute/private/local/frozen-miner-manifest.json"
~~~

This stronger gate first verifies candidate database byte length, self-reported
manifest SHA-256, absence of live WAL sidecars and SQLite integrity. It then
**requires its SHA-256 to equal the original discovery source's expected
digest**, and only then runs the literal SELECT via
SQLite `mode=ro&immutable=1`, `query_only=ON`, without external SQL
or plugin execution. It accepts exactly 3,809 non-null, unique case linkages.

If it eventually passes, the status will be
`PASS_SOURCE_LOCKED_DISCOVERY_CASE_QUERY_ONLY`: **only the archived
discovery-input identity and 3,809-case invariant** will be reproduced.
It will *not* regenerate the published 192 scanner-positive workflows,
455 producing changes, D/D7 labels, matching statistics or retrospective
interventions. Reproducing those requires separately attested source queries
and historical scanner/mapping configuration.

No database bytes were recovered, networked, committed or touched on Wits
during this source-provenance step. A candidate with a different SHA must
remain **blocked**, not patched to pass.

## 21 October — actual frozen data location traced with Wits read-only tools

The source snapshot is **not location-unknown**. Read-only SSH identity was verified as `astrauss`. The research directory at `/home-mscluster/astrauss/research_artifacts` was enumerated without writes. The final v2 discovery manifest at `full_corpus_deep_discovery_v2_20260829T181912Z/00_manifest/RUN_MANIFEST.json` records:

- **Final study source database path:** `/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db`.
- `db_sha256` **and** `expected_db_sha256`: `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`.
- `expected_cases = observed_cases = 3809`. The separate extract summary records 723 repositories and 31,223 PR-file rows. These are **historical manifest reports**, not fresh SQL results against the final-study file.
- The earlier 21 August continuation manifest distinguishes two different database files: an August 17 `hf-snapshot-20260817.db` and a later `full3809-continuation.db`. Actual **read-only COUNT(*)** queries against each of those two files returned 3,809 cases; the continuation file's non-null distinct case linkages also returned 3,809. Their SHA digests were **not checked** and they are **not interchangeable** with the final-study snapshot.
- The 21 August environment manifest records CodeQL 2.25.6, Semgrep 1.168.0, Gitleaks 8.30.1, OSV Scanner 2.4.0 and Trivy 0.72.0. These are historical **recorded** versions for the continuation phase, not a proof that the exact same binaries/queries were used for every analysis.
- The user identifies a **frozen private Hugging Face dataset**: `Stralb/malicious-issue-miner-data`, path prefix `final/full3809-scanner-complete-20260829`. Unaauthenticated public web access did not expose the private repository. No HF revision/ETag or file bytes were independently checked.
- Available Wits connector permits **read-only SQL on allowed miner database filenames** and reading text manifests, not arbitrary file hashing for the final-study path. Therefore **no fresh SHA measurement of the final file** has been performed. The exact hash remains a source+manifest expectation, rather than a verified cryptographic match to the private Hugging Face object.
- Cluster interaction in this audit was restricted to SSH reachability, identity, directory listing, two `SELECT COUNT(*)` queries and text-manifest reads. **No Slurm submissions, writes, data exports or original file changes.**

**Next gate:** independently verify the authorized Hugging Face snapshot's revision and the exact final-study database byte-level SHA, using a separately approved, read-only access method; only then rerun the archived 3,809 case-linkage SELECT and source-specific inclusion criteria. Keep `192/455/342` and all intervention claims unreproduced until their actual data and code are validated.
