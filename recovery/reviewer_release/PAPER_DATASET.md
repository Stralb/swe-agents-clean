# Paper dataset entry point

The existing review release preserves the master and historical evidence. The new exporter builds a paper-facing Parquet layer with one default entry point.

**Publication status: unverified.** Export/upload job `85293` was submitted on 11 November 2026; subsequent cluster connections timed out. Do not claim the new Hugging Face configuration exists until `ARNO_PAPER_CASES_20261111_v1/UPLOAD_RECEIPT.json` reports `REMOTE_BYTES_VERIFIED` and gives the immutable dataset commit.

## Intended entry point

Dataset: [private Stralb/malicious-issue-miner-data](https://huggingface.co/datasets/Stralb/malicious-issue-miner-data).

Configuration: `paper_cases`, the default. Physical path: `paper/arno-paper-cases-20261111-v1/cases.parquet`.

Each row is one case, keyed by `case_id`, with repository name, issue/PR URLs, issue/PR text, recorded mining metadata and explicit membership flags. The 192 finding-positive cases also have a `finding_positive_cases` configuration.

| Population | Count | Selection |
|---|---:|---|
| Full corpus | 3,809 cases | `paper_cases` |
| Finding-positive cohort | 192 cases | `in_finding_positive_cohort` |
| Initial annotations | 122 cases | `in_original122` |
| Later annotation cohort | 70 cases | `in_new70` |
| Exactly mapped | 191 cases | `in_mapped191` |
| Matched comparison | 190 pairs | `matched_pairs` configuration |
| Archived original replay records | 40 runs, 14 cases | `historical_runs` configuration |

The manuscript uses 12 complete original replay triples; the 14-case membership flag must not be interpreted as 14 complete triples.

## Supporting data

Parquet configurations keep findings, producing changes, roots, matched pairs, historical runs, later runs, original122 annotations and artifact locators separate. Join with `case_id` and scoped identifiers; these are distinct analysis units, not extra case rows. The `artifacts` table locates evidence inside the preserved SQLite master; it does not duplicate embedded binary archives.

The export reads SQLite in read-only mode. It checks the source certificate, expected cohort counts and key relationships, writes Parquet, reads each file back for equality, and verifies downloaded bytes against the local outputs after upload. It does not rehash 42 GB, reannotate cases or rerun experiments. Membership derives from named source tables rather than dates or generic mining labels. Original122 annotation fields are explicitly cohort-specific.

## Publication

The reviewed [exporter](build_paper_dataset.py) and [job wrapper](paper_entrypoint.sbatch) preserve the exact implementation. The job uses isolated dependencies. The Hugging Face root dataset card will declare explicit configurations, preserve unrelated prior metadata and archive the previous card. Older data files remain untouched and are excluded from automatic default loading. No full-database upload completion is implied.

After successful publication, use the commit in the upload receipt:

```python
from datasets import load_dataset
cases = load_dataset('Stralb/malicious-issue-miner-data', 'paper_cases', split='train', token=True)
positive_cases = cases.filter(lambda row: row['in_finding_positive_cohort'])
```

The `train` split is a storage convention; it is not a training/evaluation allocation. Pin `revision` to the verified receipt commit for reproducible analyses. Scanner findings are not confirmed exploitable vulnerabilities.
