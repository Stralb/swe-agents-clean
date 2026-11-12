# Arno Research Reproducibility

Private working repository for reconstructing, auditing, and reproducing the malicious-GitHub-issue / coding-agent security research programme.

> **Status: recovery and verification in progress.** This repository is not yet a validated replication package. Do not interpret a discovered script, an archive named `FINAL`, or a reported historical result as independently reproduced.

## Research scope

The complete research history includes:

1. GitHub issue-to-agent-associated pull-request mining and AI-agent identification.
2. Security scanning, scanner finding normalization, before/after comparisons, and production-change attribution.
3. Manual review and attack-footprint analysis, including the historical 122-case evaluation and F1-F5 workstreams.
4. Full-corpus discovery, NEW70 blind review and validation stages.
5. The root-decision census, evidence provenance, independent coders, adjudication and D7 holdout.
6. Matched workflow controls, decision-level controls and robustness analyses.
7. Historical replay, issue interventions, ablation experiments, T1/T2 and O/W/P prevention experiments.
8. Positive, negative, failed, incomplete, and superseded runs.

The *units of analysis* (workflows, findings, producing changes, roots, paired controls and intervention generations) must remain distinct.

## Source-of-truth rules

- Preserve all original inputs and frozen observations. Never silently edit them to make the results consistent.
- Every imported source and result must be identified by origin, retrieval date, SHA-256 digest, version, and experimental role.
- Track implementation state separately from scientific validity: `candidate`, `verified`, `frozen`, `exploratory`, `superseded`, `buggy`, or `unresolved`.
- Prefer proven fixes and tested outputs over filenames such as `latest` or `final`.
- Keep contradictory frozen results separate pending adjudication. In particular, D-final and D7 require row-level reconciliation.
- Document unreproducible results and failed experiments explicitly.
- Exclude secrets, SSH keys, credentials, personal information and large bulk data from Git; reference approved external artifacts with checksummed manifests instead.

## Wits cluster safety boundary

The existing Wits research files and job state are **not** a writable workspace for this repository.

- Do not delete, rename, replace, truncate or mutate any original research files.
- Do not submit, cancel or modify cluster jobs without explicit, case-specific authorization.
- Cluster inspection is read-only by default.
- Any future write, if authorized, is create-only inside a new, isolated project path; do not operate on the original source trees.
- Do not push to `michaelpradel/malicious-issue-study` or any other third-party repository without explicit permission.

## Proposed structure (to populate after auditing)

```text
src/                 Recovered and validated production/analysis source
experiments/         Versioned experimental runners, inputs and manifests
analysis/            Statistical and qualitative analysis
tests/               Unit, integration, data and replication checks
configs/             Version-pinned experimental configurations
data/                Schemas, public samples and external data manifests
results/             Verified small derived outputs and result registries
provenance/          Checksums, artifact lineage, correction ledger
historical/          Immutable superseded/failed code and protocol records
docs/                Research timeline, codebooks, methods and limitations
```

This structure is **planned**, not evidence that these directories or their contents have already been recovered or tested.

## Initial recovery inputs

Researcher-provided materials include a live read-only miner export, August source snapshots, historical root-census and provenance archives, matched-control artifacts, full-corpus discovery archives, T1/T2 packages, and October prevention handoffs. File-by-file ingestion and provenance validation will be recorded as work proceeds.

## Release gate

Before calling this repository peer-review-ready, demonstrate:
1. Source provenance and artifact integrity.
2. Reproduction of cohort counts and frozen analytical datasets.
3. Independent verification of reported statistical tables and contrasts.
4. Validity of scanner rules, baselines, patch generation, and evaluation inputs.
5. Environment/version pinning, runnable tests, and documented limitations.
6. A complete history of known defects, corrections, and unsuccessful experiments.

**No scientific result has been independently certified by this initial commit.**

## October O/W/P archive audit

The archived CodeQL-after results and functional-check intake are now covered by a separate [read-only reproducibility checker](tools/owp14_archive_audit.py) and a [scientific evidence audit](docs/OWP14_EVIDENCE_AUDIT_20261020.md). This work verifies exact ZIP member hashes and cross-checks recorded case-level results, but **does not yet reproduce the new-alert delta from baseline SARIF or prove functional/causal outcomes**. The case-level [source-labelled observations](provenance/owp14_case_arm_counts_20261020.csv) remain exploratory.

## October O/W/P generation provenance and patch scope

See the [generation/patch lineage audit](docs/OWP14_PATCH_AND_GENERATION_LINEAGE_AUDIT_20261020.md). Two new **read-only** checkers (`tools/owp14_generation_lineage.py` and `tools/owp14_patch_scope.py`) verify original patch transfer, the 40 patch-to-CodeQL links, 65-case screening versions, job source inventory and patch-size contrasts. Exact member digests and case-level scope measurements are tracked under `provenance/`.

These checks establish archival linkage and descriptive implementation differences; they do **not** establish independent model-generation cohorts, complete task acceptance, a reconstructed CodeQL new-warning baseline, a prospective safety-information retrieval mechanism, or a causal prevention result.

## Historical source-code recovery

Recovery of the original miner and experiment drivers is tracked in [the source-only recovery intake](docs/SOURCE_RECOVERY_STATUS_20261020.md). A separately prepared, SHA-256 verified package contains 1,075 historical source files from seven archives; it is **pending import on a review branch**, not yet a verified active miner. Use [`tools/verify_source_snapshot.py`](tools/verify_source_snapshot.py) to verify its per-file manifest without executing any historical script.
