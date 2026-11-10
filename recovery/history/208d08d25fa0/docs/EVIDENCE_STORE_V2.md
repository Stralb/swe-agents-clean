# Reproducibility evidence archive — implementation v2

**Target repository:** `Stralb/arno-research-reproducibility` (independent of historical miner).
**Source-data policy:** Original Wits/HF research data is READ ONLY. This archive is
created separately and imports exact bytes without mutating original files.

## What changes in v2

The original `EvidenceStore` v1 indexes opaque files by SHA-256. v2 adds:

- Source-recorded structured rows (`research_records`) and historical labels
  (`research_annotations`), indexed by case, finding and producing-change ID.
- Explicit relationships (`research_edges`) such as producing change → finding
  and finding → workflow. Unmatched sources remain visible.
- Archive-member preservation (`archive_members`). Every allowed ZIP/TAR member
  is stored as exact bytes in the vault and indexed by its original path.
- Strict experiment run crosswalks (`experiment_runs`, `experiment_run_assets`).
  No patch is attributed to a run, condition, scanner outcome or model unless
  **an explicit source manifest** supplies that mapping.
- An evidence gap registry (`evidence_gaps`). A missing patch/scanner result is
  never interpreted as a failed/pass/zero finding.
- Offline release preflight and opt-in **private** Hugging Face publication.

### Reviewer retrieval model

```
One logical private evidence vault
  catalog.sqlite                    # immutable small bytes AND relational records
  objects/<sha-prefix>/<sha-tail>  # exact bytes of larger binary artifacts

workflow 154
  -> recorded issue/body/implementation/risk annotations
  -> CF-0002 (finding in workflow)
  -> PC-0001 (producing change in workflow; produced finding CF-0002)
  -> original workbook bytes and lineages
  -> future root ID via C crosswalk intake
  -> future run records plus true patch bytes via explicit run manifest
```

This logical vault is **not** a single monolithic SQLite file. Small text
patches are stored directly in SQLite BLOBs; very large diffs, original
archives, source-tree snapshots and SARIF files are content-addressed blobs
inside the **same pinned HF dataset revision**, retrievable by SHA from the
query API. Metadata-only links without accessible bytes are not considered
complete ingestion.

## Local commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m src.repro_store.research_cli init /path/to/NEW_PRIVATE_VAULT
python3 -m src.repro_store.research_cli import-workbook /path/to/NEW_PRIVATE_VAULT \
  '/path/to/issue_pr_manual_evaluation_master_122.xlsx' \
  --origin-uri 'researcher-upload://original-master-workbook' \
  --origin-revision 'sha256:<exact-source-digest>' \
  --expected-sha256 '<exact-source-digest>'
python3 -m src.repro_store.research_cli import-archive /path/to/NEW_PRIVATE_VAULT \
  /path/to/APPROVED_EXPERIMENT_ARCHIVE.zip \
  --origin-uri 'wits://research_artifacts/<precise-relative-path>' \
  --origin-revision 'frozen-source-copy:2026-10-25' \
  --expected-sha256 '<hash-of-approved-archive>'
python3 -m src.repro_store.research_cli register-runs /path/to/NEW_PRIVATE_VAULT \
  /path/to/EXPLICIT_RUN_MANIFEST.json \
  --origin-uri 'researcher-controlled://run-manifest-v1' \
  --origin-revision 'sha256:<manifest-hash>'
python3 -m src.repro_store.research_cli import-csv /path/to/NEW_PRIVATE_VAULT \
  /path/to/C2_MATCHED_PAIRS_FROZEN.csv \
  --origin-uri 'wits://research_artifacts/matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv' \
  --origin-revision 'sha256:<hash>' --expected-sha256 '<hash>' \
  --stage C2 --unit-type control_pair \
  --key-column positive_case_id --key-column control_case_id \
  --relate positive_case_id workflow positive_side \
  --relate control_case_id workflow control_side
python3 -m src.repro_store.research_cli case /path/to/NEW_PRIVATE_VAULT 154
python3 -m src.repro_store.research_cli verify /path/to/NEW_PRIVATE_VAULT
python3 -m src.repro_store.hf_release /path/to/NEW_PRIVATE_VAULT
```

The last command is **offline only** by default; no HF token needed.
Install the optional isolated dependencies with
`python3 -m pip install -r requirements-repro-evidence.txt` inside a new
virtual environment. Keep the original miner environment separate.

Reviewer SQL against the already ingested private catalog:

```sql
SELECT stage, label_name, label_json, verification
FROM reviewer_annotations
WHERE unit_type='workflow' AND unit_id='154'
ORDER BY stage, label_name;

SELECT from_type, from_id, to_type, to_id, relation
FROM research_edges
WHERE (to_type='workflow' AND to_id='154')
   OR (from_type='workflow' AND from_id='154');

SELECT study_id, run_id, arm, evidence_role, artifact_sha256
FROM reviewer_experiment_assets
WHERE study_id='T1-context-pilot';
```

Data values from `reviewer_annotations` are preserved source observations,
not new human verification. A reviewer retrieving a digest uses
`python3 -m src.repro_store.research_cli export-artifact <vault> <sha256> <new-output-path>`.
 It prints
an immutable release prefix and local hash manifest. Publication requires
explicit `--execute --acknowledge-private-review`, a private HF dataset,
validated rights, correct account/permissions and sufficient quota. No upload
occurred during implementation or testing.

## Sample experiment run crosswalk

```json
{
  "schema_version": 1,
  "source_archive_sha256": "<64-hex-archive-sha>",
  "study_id": "T1-context-pilot",
  "protocol_revision": "frozen-T1-version",
  "runs": [
    {
      "run_id": "G001",
      "case_id": "3592",
      "arm": "Context+",
      "seed": 1,
      "model": "<exact-model-id-and-version>",
      "base_commit_sha": "<exact-git-base>",
      "files": {
        "prompt": "input/G001/TASK.md",
        "generated_patch": "patches/G001.patch",
        "scanner_after": "scanner/G001.sarif",
        "functional_result": "eval/G001.json"
      }
    }
  ]
}
```

The example is *schema illustration*, not an asserted mapping for historical
G001. A real manifest must be built from verified input/run crosswalk files;
no mapping from a filename alone is acceptable.

## Mandatory paper-grade gates

1. Freeze the complete **3,809** workflow source snapshot (source SHA and HF
   commit revision), then independently rerun original membership filters.
2. Import both positive and scanner-negative workflows, preserved original
   scanner before/after status, all genuine raw/canonical findings and 455 PCs.
3. Import 342 roots and both D-final / D7 original classifications as **distinct
   versions**, with all unresolved root differences intact.
4. Import C6 190-pair raw decisions, 31 primary decision pairs, and original
   prompts/patches/failed and negative outcomes.
5. Collect full generation artifacts: model/config/seed, baseline commit,
   intervention arm, prompt, code patch, scanner rule+SARIF, functional result,
   stderr/stdout and adjudication/corrections.
6. Reconcile missing/incorrect scanner baselines, 43 D/D7 differences,
   ambiguous original source identities and rights/privacy limits.
7. Pin HF release commit SHA and rerun every statistical output without using
   historical reported metrics as ground truth.

**Current deployment status:** Source code tested offline; one real historical
workbook has been indexed in a separate private local vault. No Wits write,
Slurm job, HF upload or GitHub branch modification occurred in this delivery.
The local index is not the entire project corpus or a peer-reviewed release.
