# Recovery, Version Control and Reproduction Protocol

## Workspace boundaries

This GitHub repository is **new and independent**. It is not the Michael Pradel repository and is not a clone of the live Wits miner.

- Original cluster trees, databases, repository caches, historical Git objects and experiment outputs remain read-only.
- No cluster deletion, overwrite, rename, reset, cleanup, force-push, or job operation is permitted by this protocol.
- New source on GitHub goes through independent commits/PRs with descriptive provenance and tests. No raw third-party private repositories, secrets, tokens, credentials, personal data or bulky generated outputs are imported as source.
- Creation of a new cluster workspace or submission of a new Slurm job requires separate explicit approval, even when paths look safe.

## Staged recovery procedure

1. **Locate:** identify original archive/cluster path and retrieval channel. Record filename, byte count and SHA-256.
2. **Assess:** check archive member paths, duplicate names, symlinks, sensitive content, source licences and size. Do not extract archives blindly.
3. **Classify:** assign exact analytical unit and status: `historical`, `frozen`, `exploratory`, `superseded`, `known-bug`, `unverified`, `verified` or `conflicted`.
4. **Compare:** when multiple candidates exist, compare code, inputs, outputs, schema and corrections; never pick by modification time alone.
5. **Promote:** only candidate code with trustworthy provenance and meaningful checks may enter active `src/`. Reuse tests and document deliberate changes.
6. **Reproduce:** run from a clean checkout against a frozen, hash-verified data copy or a documented small fixture, with exact command, Python/tool version, dependencies, random seed and expected outputs.
7. **Report:** distinguish *archive intact*, *syntax passing*, *runs successfully*, *tables reproduced* and *causal claim supported*. These are separate levels.

## Local verification (does not touch the cluster)

Use Python 3.10 or newer. The checker uses only Python's standard library.

```bash
python -m unittest discover -s tests -v
python tools/recovery_audit.py verify-manifest provenance/artifact_register.csv /path/to/local/uploaded_archives
python tools/recovery_audit.py audit-census '/path/to/C_ROOT_CENSUS_FINAL_v1.0.tar.gz'
python tools/recovery_audit.py compare-d '/path/to/D_FINAL_COMPLETE_ROOT_PROVENANCE_v1.0.tar.gz' '/path/to/D7_DISCOVERY_HOLDOUT_BUNDLE_GPT56SOL_v1.0.tar.gz'
```

The manifest records the **exact uploaded basenames** (which can include `(1)`/`(2)` suffixes), so use the actual recovered copies when running checksum checks. A missing or changed archive is explicitly reported; files are never automatically downloaded, repaired or overwritten.

The `compare-d` command returns `UNRESOLVED_DIFFERENCE` and exit code 0 when the comparison **successfully detects a real difference**. It returns nonzero on malformed or structurally incompatible evidence. A zero exit code is not a conclusion that D and D7 agree.

## Promotion gate for a publication-ready artifact

- Source version pinned to a specific content hash; no unreviewed merge of scripts.
- Data origin, inclusion/exclusion logic and analytical unit independently checked.
- Scanner baseline, suite/version, target-match logic and suppression/false-positive policies audited.
- Exact intervention inputs and patch generation conditions frozen before evaluation; no generation/annotation leakage.
- Reported metrics, denominators, confidence intervals and p-values regenerated with recorded code and seeds.
- Negative, incomplete, missing, failed and superseded results archived without selective deletion.
- Distribution approved for source licences, credentials, sensitive code, reviewer blinding and third-party data rights.
