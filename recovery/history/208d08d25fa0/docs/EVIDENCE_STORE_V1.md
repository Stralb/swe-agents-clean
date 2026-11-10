# Research evidence vault (experimental implementation)

This is an isolated, local, append-only catalog inside the **independent**
`Stralb/arno-research-reproducibility` repository. It is **not** the historical
`malicious-issue-miner-rate-smart` SQLite and must never be opened with the old
miner `Database` class or automatic migrations.

## Design

An individual paper case can link together its immutable issue text, real PR
patch, exact baseline and head scanner output, canonical finding, producing
change, final root decision, blind coding record, adjudication, matched controls,
model-generation inputs, code and configuration, generated patch, and tests.

Each file is addressed by SHA-256, not its current filename. A `source` records
where its bytes came from and which source revision they represent. A `link`
connects that source to a `workflow`, `finding`, `producing_change`, `root`,
`control_pair`, `generation`, `run`, `cohort` or `claim` ID. A `derivation` connects
one immutable artifact to a later one through a specified code revision.
A correction is **a new artifact and new source/link**, not an edit of a frozen
result. Preservation of blind and unblinded evidence requires separate links
and access control at the deployment layer.

Files <= 1 MiB go in `catalog.sqlite` as BLOBs. Larger files go in immutable
`objects/<digest>` files, with their reference in SQLite. Both components
are part of one logical dataset and must be archived together. This prevents
thousands of very large diffs/repositories from making every catalog read
require streaming a massive SQLite BLOB database. A peer reviewer can query
by `unit_type` + `unit_id` and resolve the *exact* artifact bytes by hash.

## Local smoke example (no cluster/Hugging Face access)

```bash
python3 -m unittest tests.test_repro_store -v
python3 -m src.repro_store.cli init /tmp/new-evidence-vault
python3 -m src.repro_store.cli ingest /tmp/new-evidence-vault /path/to/approved/file \
  --origin-uri 'wits://research_artifacts/path/to/file' \
  --origin-revision 'frozen-manifest-sha256:...' \
  --expected-sha256 '<expected-file-sha256>'
python3 -m src.repro_store.cli link /tmp/new-evidence-vault 1 \
  --unit-type root --unit-id CROOT-03592-01 --role historical-patch \
  --stage C --blinding unblinded --method-revision 'C-v1.0'
python3 -m src.repro_store.cli find /tmp/new-evidence-vault \
  --unit-type root --unit-id CROOT-03592-01
python3 -m src.repro_store.cli verify /tmp/new-evidence-vault
python3 -m src.repro_store.cli manifest /tmp/new-evidence-vault
```

Never run this on the source directory or active miner SQLite. This MVP
copies source bytes into a separately created vault and leaves originals
unchanged. It refuses an existing output directory and large input files
unless `--allow-large` is explicitly specified. SHA verification occurs at
intake and audit. A manifest describes exact stored bytes and source lineage.

## Hugging Face design (NOT deployed)

The intended remote is the **existing private dataset**
`Stralb/malicious-issue-miner-data`; this code does **not** assume that its
current revision or raw SQLite hash has been verified. We have not uploaded,
replaced or downloaded any Hugging Face object.

After authorizing each source and checking redistribution/licence/privacy,
publish a consistent SQLite backup and all referenced `objects/` under one
immutable HF dataset commit. Record dataset revision SHA and exact per-file
hashes in a release manifest. Never expose credentials in Git or logs. Use
read-only `snapshot_download(..., revision=<commit_sha>)` and `verify` in
reproduction. A separate HF adapter still needs integration and tests before
this workflow can run unattended.

## Research validity boundaries

- Hash agreement establishes identity, **not** scanner correctness or proof
  of vulnerability.
- An original warning and a derived patch must be linked to their correct
  base/head Git SHAs, scanner/query version and changed code lines.
- The 3,809/192/455/342/233 cohorts have distinct units and must not be
  conflated into a single `cases` table.
- D-final versus D7 disagreements remain separate frozen evidence until
  source-grounded adjudication.
- Historical positive/negative controls, failed generations, missing files,
  selection protocols, seeds, prompts and null results belong in the catalog.
- Evidence with unknown rights, secret content or personal information must
  stay restricted; `approved-for-release` is never inferred automatically.

**Status:** Tested local evidence-store prototype. **Not** a completed corpus
import, remote HF synchronization, independent scientific reproduction,
cluster job, or paper-ready public dataset.
