# adversarial-swe-agents

**Database filename:** `adversarial-swe-agents.sqlite`.

Start with the [private Hugging Face dataset](https://huggingface.co/datasets/Stralb/adversarial-swe-agents). Its default configuration, `paper_cases`, contains one row per issue–PR case, with repository names, source text, URLs and explicit paper-cohort flags.

**Verified data revision:** `e71e8b39ed56ffb1c2198b9df2384495b8404317`.

| Data | Size |
|---|---:|
| Default case index | 3,809 cases |
| Finding-positive cohort | 192 cases |
| Initial / later annotation cohorts | 122 / 70 cases |
| Cases with mapped changes | 191 cases |
| Producing changes | 455 changes |
| Final implementation roots | 342 roots |
| Matched comparison | 190 pairs |
| Archived original replay records | 40 runs across 14 cases; 12 complete triples |

The ten Parquet configurations keep cases, positive cases, changes, roots, pairs, annotations, findings, original runs, later runs and artifacts as distinct analysis units. The release manifest records schemas, row counts, source qualifications and file hashes.

```python
from datasets import load_dataset

cases = load_dataset(
    "Stralb/adversarial-swe-agents",
    split="train",
    revision="e71e8b39ed56ffb1c2198b9df2384495b8404317",
    token=True,
)
```

The `train` split is a storage convention, not a training/evaluation allocation. Private access is required.

## Evidence and historical files

The cleanup verified the identities of all 154 files retained under `archives/`. Previous revisions are also retained through preservation refs. No access permissions or Git history were rewritten.

The artifact interface uses stable SHA-256 IDs and neutral table aliases. The release's `resolve_artifact.py` recovers the exact source record from the preserved SQLite snapshot. Source rows and archives retain their original bytes; the source-text exception register documents remaining historical wording in verbatim case and annotation text. Author credits are preserved.

The [completion receipt](HUGGINGFACE_RELEASE.json) attests remote file checks and successful loading of the 3,809 cases and 190 matched pairs. It **does not attest completion of the full master SQLite upload**.

## SQLite preparation

[SCHEMA.sql](SCHEMA.sql), the [ERD](erd/OVERVIEW.svg) and [builder](build_dataset.py) describe a prepared neutral derivative containing 111 tables and 18 views. That derivative has not been verified as built or uploaded. These schema artifacts must not be presented as the deployed schema of the original operational master.

The verified Hugging Face Parquet schemas are those recorded in its release manifest. The database content is unchanged. Its canonical filename is `adversarial-swe-agents.sqlite`; a compatibility alias keeps older local scripts working.

[Dataset exporter and cleanup](clean_hub.py) · [Cluster launcher](run_hub_cleanup.py)
