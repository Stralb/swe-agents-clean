# Research dataset and reviewer release

The Arno reviewer edition packages the preserved mining and research evidence in
one SQLite database, with an added review layer and small CSV exports. It retains
the original evidence and historical status records; it does not re-annotate the
study or establish that every recorded experiment is scientifically valid.

## Release and access

| Item | Value |
|---|---|
| Release | `ARNO_REVIEW_RELEASE_20261111_v1` |
| Format | SQLite plus CSV, SQL, JSON and Python utilities |
| Database | `ARNO_RESEARCH_MASTER_REVIEW.sqlite` |
| Database size | `42,187,345,920` bytes |
| Database SHA-256 | `b9734456db5b6c1abb1ef72ec146eb4db2cacbb75115b64cfae34b95223d5011` |
| Dataset repository | [Stralb/malicious-issue-miner-data](https://huggingface.co/datasets/Stralb/malicious-issue-miner-data) — **private; authorised Hugging Face access required** |
| Release folder | [`research/arno-review-20261111-v1`](https://huggingface.co/datasets/Stralb/malicious-issue-miner-data/tree/main/research/arno-review-20261111-v1) |
| Verified reviewer-file revision | `f37aa902fd48c8b2b4e5ed489c7b5f9beae32b48` — covers the guide, dictionaries, CSVs and checks, not a verified full database upload |
| Transfer status | [BUILD_STATUS.json](BUILD_STATUS.json). After full database verification, use the dataset's `CURRENT_RESEARCH.json` and release `UPLOAD_RECEIPT.json` for the pinned database commit. |

The database hash above identifies the locally verified release. Do not infer that
the full database transfer is complete from the presence of the smaller files.
For a paper or frozen analysis, record the exact dataset commit, database filename,
SHA-256 and relevant code commit, rather than citing only a moving `main` link.
Private access must be arranged for reviewers; a public code-repository link does
not itself provide access to the data.

## What the cleanup changed

| Preserved | Added or organised |
|---|---|
| All **127 original tables**, including SQLite's internal sequence table; original fields, labels and archived payloads | **8 `review_*` catalog tables** and **18 `review_v_*` views** |
| Original annotation/event and experiment records | Case/run/artifact navigation, column and relationship catalogs, and a quality-issue register |
| Both historical claims and later correction records | A claim-status view that applies only explicitly documented supersession to matching claim IDs |
| Original archived O/W/P experiments and later tests | A run catalog that separates their provenance and prevents later O generations being treated as recovered historical O arms |
| Preliminary and final source records | Separate final-facing and historical/preliminary views and CSV exports |
| Embedded evidence-vault bytes already merged into the master | An index of **670 artifact records**; this count includes representations/locators and is not a count of unique experiments |

The original cluster master was not modified. No original experiment, annotation
label or uncertainty was deleted or silently corrected. This was an additive
documentation and review-access cleanup, not a physical normalisation or semantic
rewrite of every original table. The standalone vault is not required for using
this release: all 52 of its evidence objects were previously byte-verified inside
the master.

## Structure and identifiers

The completed reviewer database contains **135 tables**: 126 original application
tables, 8 new review catalogs and 1 SQLite internal table. It has **25 views**:
7 original views plus 18 new review views.

- [Full-database ERD, including disconnected tables](database/erd/FULL_DATABASE_ERD.svg).
- The downloadable release also includes `tables/table_catalog.csv`,
  `tables/column_catalog.csv`, `tables/relationships.csv` and `tables/artifacts.csv`.

`case_id` is the stable issue/PR-case key; `run_id` is the experiment key. Use
`cohort` together with `producing_change_id`. Preliminary and final canonical
finding IDs represent different versions and must not be merged by bare ID.
Cases, scanner findings, producing changes, root decisions and experimental runs
are different analysis units.

ERD arrows represent **declared SQLite foreign keys**, not all logical links in
JSON, archive filenames or prose. The diagrams do not establish historical FK
enforcement or validate every row-level relationship.

## Which records should an analysis use?

Later dates alone confer no priority. An explicit, source-backed correction can
supersede the matched claim's older audit status; both records remain visible.
An audit marked "source verified" establishes the stated provenance, not the
scientific truth of all labels in that source.

| Experiment class | Runs | Default interpretation |
|---|---:|---|
| Archived original O/W/P conditions | 40 | Historical evidence candidates; requires the original protocol and its qualifications |
| Later analysis of historical patches | 7 | Supplementary; not the historical scanner invocation |
| Later baseline scans | 7 | Supplementary baseline records |
| Later architectural experiments | 12 | Supplementary, distinct experiment family |
| Later non-blind new O generations | 2 | Supplementary; do not fill the missing historical O arms |

The 40 original O/W/P conditions cover 14 cases, with 12 complete original triples.
This cleanup does not automatically select a paper's primary analysis or reject
a run simply because it is newer. Use `review_v_runs`, the preserved protocol and
source qualifications to state an explicit inclusion rule.

## Inspecting the release

The `data/` CSVs export the case registry, original-122 annotations, final NEW70
findings, NEW70 case-risk source, producing changes, final root coding, matched
pairs, recorded statistical reproductions and run catalog. `history/` separately
exports annotation events, preliminary candidates and claim/status history.
`CSV_EXPORTS.json` records each export's source table/view, columns and row count.
Binary payloads remain in the SQLite database and are located through the artifact
index; they are not converted to CSV strings.

From the complete downloaded release directory:

```sh
sha256sum -c SHA256SUMS
sqlite3 -readonly -header -csv ARNO_RESEARCH_MASTER_REVIEW.sqlite < REPRODUCE.sql
python3 artifact_reader.py list --case 3429
python3 artifact_reader.py list --run OWP14_CASE03429_O
```

Python's standard library is enough for the extraction utility. The SQL command
requires the SQLite CLI. Graphviz is needed only to regenerate the diagrams, not
to read the data. [WORKED_CASE.sql](WORKED_CASE.sql) illustrates how case 3429's
three archived arms remain separate from its later analyses and generations.

## Validation and remaining qualifications

- The original input snapshot passed a full SQLite integrity check. Its complete
  copy was verified by SHA-256 before the review layer was added.
- Original schemas and targeted research/view counts were checked. Original row
  counts in the catalog come from the verified snapshot certificate; large
  operational tables were not all recounted after the additive cleanup.
- The finished review database has the checksum shown above. **16 descriptive SQL
  queries ran and all 10 sampled artifact extractions passed**. These were samples,
  not an independent re-validation of every indexed artifact.
- All **12 CSV exports** were created. The smaller reviewer files were checked
  against remote sizes and content hashes/Git blob identities after upload.
- `REPRODUCE.sql` reproduces descriptive counts and exposes recorded evidence;
  it does not rerun the entire mining corpus or all historical experiments.
- Empty prompt fields do not prove prompts are absent from archives. Complete
  invocation traces, independent human-review provenance, generator identity,
  functional equivalence and causal prevention remain qualified by source evidence.
- Scanner findings are not automatically verified exploitable vulnerabilities.
  Packaging does not resolve missing historical evidence or certify a full export
  of the ChatGPT project's conversations.

## Citation and reuse terms

When using the data, cite the associated research report or paper and identify the
release, pinned dataset commit and checksum. Formal paper citation metadata and a
dataset licence were not assigned by this cleanup; add them explicitly before
claiming a public reusable dataset release. No licence for third-party source
archives is inferred from the code repository's licence.
