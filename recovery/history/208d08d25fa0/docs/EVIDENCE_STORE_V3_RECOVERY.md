# Research evidence vault v3: source-grounded recovery checkpoint

**Repository:** `Stralb/arno-research-reproducibility` (NOT the original miner)
**Recorded:** 2026-10-25
**Data:** private; unblinded keys and third-party source content require separate review

## What this implementation actually does

1. Retains the original 122-case master workbook byte-for-byte. Indexed rows,
   historical classification passes and case/finding/producing-change edges
   can be queried without opening Excel; these are **source-recorded** labels,
   not an independent recoding of original research.
2. Ingests **six original, byte-verified S5PAIR-001 blinded metadata files**:
   - `input/BLINDED_MANIFEST.csv` (12 run rows, SHA-256
     `38cf059f62e77d724dcd611da30b866adb85a49ca6164a10cf3746c422293b38`)
   - `input/BASE_SHA256.txt`
   - `input/README.txt`
   - `results/BLINDED_CODEQL_SUMMARY.csv` (12 run rows)
   - `results/BLINDED_CODEQL_FINDINGS.csv` (header only)
   - `results/STEP4_QC.json` (source-reported `PASS`)
   Exact bytes were recovered via the read-only V6 connector, and their local
   SHA-256 hashes matched the connector hashes. Historical scanner outputs
   were **not independently rerun**.
3. Records **56 S5PAIR source expectations** for patches, reports, original
   output ZIP hashes, run SARIF, source baselines and shared metadata, plus
   **18 core source candidates** for C1/C2/C6 controls, 455 producing changes,
   342-root evidence, NEW70, and the 31-case audit. An expectation is **not**
   the underlying source byte. The separate `expected_evidence` table is
   append-only; if exact bytes are later imported, the coverage query can
   automatically prove availability via content hash.
4. Supports `case-dossier` for source-recorded workflow/finding/change graphs,
   and `run-dossier` for source-recorded run metadata versus full explicit
   file-to-run associations. It never infers intervention arms, seed, model or
   case identity from the blinded G001-G012 identifiers.
5. Provides a create-only S5PAIR replay packer that, when run with read access
   to the ORIGINAL replay folder, checks all 12 patch/report SHA-256 values,
   checks the common original base snapshot SHA, includes complete per-run
   scanner SARIF, source summary/QC, and creates a derived archive plus an
   explicit (still blinded) run-to-asset crosswalk. No cluster write, jobs or
   code execution are performed by the packer.

## Real private local vault state

- Historical 122-case source rows: **4,371** (from the earlier stage).
- V3 source rows: **25** (12 run-manifest + 12 scanner-summary + 1 QC).
- Total source rows: **4,396**.
- Original source files present with locally validated SHA-256: **6** S5PAIR
  metadata files (plus the preserved original 122 workbook).
- S5PAIR expectations: **56**; **6** present with verified bytes, **37** with
  expected hashes but bytes not copied, **13** with insufficient source digest.
- Actual S5PAIR patch bytes in vault: **0 / 12**.
- Actual per-run S5PAIR scanner SARIF bytes in vault: **0 / 12**.
- Explicit S5PAIR treatment-to-case/run crosswalks: **0**. The study remains
  **blinded**. Original output ZIP SHA values do not establish the location or
  availability of those ZIP files.
- All tests: **50 passing offline** as of this checkpoint.

Note: patch-application `PASS`, absent target warning, and zero scanner findings
linked to added lines are historical scanner *reports*, not correctness tests,
proof of vulnerability absence, or a publishable causal finding.

## Query today's private local vault

```bash
cd /path/to/arno-research-reproducibility
export PYTHONPATH=.
python3 -m src.repro_store.research_cli verify /path/to/PRIVATE_VAULT
python3 -m src.repro_store.research_cli case-dossier /path/to/PRIVATE_VAULT 154
python3 -m src.repro_store.research_cli run-dossier /path/to/PRIVATE_VAULT S5PAIR001_STEP4_BLINDED G001
python3 -m src.repro_store.research_cli expectations-coverage /path/to/PRIVATE_VAULT S5PAIR001_STEP4_BLINDED
python3 -m src.repro_store.research_cli expectations-coverage /path/to/PRIVATE_VAULT FROZEN_CORE_DATA_RECOVERY
```

The source-observation-only run dossier is intentionally NOT a generation
record with a stored patch. The reviewer can see exact manifest patch hashes,
raw scanner-summary values and the missing-file statuses.

## Ingest the complete original blinded replay once the cluster source is mounted

All paths are illustrative of the original known source root; no script below
was run on Wits, and its source must be read-only. Run inside a distinct,
researcher-authorized, isolated environment with access to source bytes.

```bash
python3 -m src.repro_store.replay_intake \
  /home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/step4_blinded \
  /path/to/NEW_PRIVATE_STAGING/S5PAIR001_stage
python3 -m src.repro_store.research_cli import-archive /path/to/PRIVATE_VAULT \
  /path/to/NEW_PRIVATE_STAGING/S5PAIR001_stage/S5PAIR001_STEP4_BLINDED_SOURCE_EVIDENCE_DERIVED.zip \
  --origin-uri 'derived-from-wits://counterfactual_replay_r1/step4_blinded' \
  --origin-revision 'original-source-frozen-20261025'
python3 -m src.repro_store.research_cli register-runs /path/to/PRIVATE_VAULT \
  /path/to/NEW_PRIVATE_STAGING/S5PAIR001_stage/RUN_CROSSWALK_BLINDED.json \
  --origin-uri 'derived-from-wits://S5PAIR001_RUN_CROSSWALK_BLINDED.json' \
  --origin-revision 'archive-sha256-from-INGEST_AUDIT.json'
python3 -m src.repro_store.research_cli verify /path/to/PRIVATE_VAULT
python3 -m src.repro_store.research_cli study-coverage /path/to/PRIVATE_VAULT S5PAIR001_STEP4_BLINDED
```

The packer has synthetic tests, including tampered hash failure, symlink
rejection, partial scanner handling and refusal to overwrite existing outputs.
A **complete** local source is required by default. An incomplete capture
requires a deliberate `--allow-missing-scans` or `--allow-missing-base`, and
its output audit must list every source gap.

## Hard blockers to paper-grade evidence completeness

1. Get exact bytes of the 12 replay patches, 12 reports, 12 per-run SARIF,
   original base and base SARIF; then locate original generated output ZIPs.
2. Recover original task prompts, model/seed/config, generated patch provenance
   and true functional outcomes. Blinded conditions must not be unblinded
   before the independent evaluation is frozen.
3. Import the canonical frozen 3,809-workflow source database (complete
   source SHA must be checked against the source manifest), and establish
   exact F1-F5, 192/191/455/342 lineage from database queries.
4. Import and preserve separately C2 (190 pairs), C6 raw paired decisions,
   D original coder passes, D-final and D7 as distinct versions. Do **not**
   overwrite the documented 43 D/D7 disagreement roots with heuristics.
5. Recover missing original CodeQL before-SARIF baselines for the 14 O/W/P
   replay cases; label cases with absent baseline as **not verified**.
6. Import other generation campaigns, false leads, failed patches and null
   results, with source-original prompts/config, hashes, model versions,
   scanner outputs and test outcomes.
7. Private/HF release: review exposure and IP rights, preserve blind separation,
   publish to a **private** immutable versioned prefix, pin the exact HF
   commit SHA, then independently download/verify all required bytes before
   making a full-reproducibility claim.

**As delivered:** no writes to the original Wits source, no Slurm submission, no
Hugging Face upload, no GitHub main merge. Local metadata source integrity
passes, but full experiment evidence completeness does not.
