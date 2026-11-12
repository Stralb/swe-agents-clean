# Frozen C1→C2→Phase1→C/D root population lineage

## Current evidence level

**Recorded, cross-audited study aggregates — NOT independently rederived
research observations.** The information below was read using restricted,
read-only Wits tools on 21 October 2026. No historical source was edited,
no scanner executed on a live repository, no Slurm job started, and no
case-level, repository-level, issue or PR data was copied into Git.

`provenance/cluster_stage_lineage_20261021.json` records only
nonsensitive stage totals, source paths and publicly harmless content hashes.
The audit at `analysis/cluster_stage_lineage.py` checks the stage
identities and accounting invariants; it does NOT claim that a recorded JSON
object independently validates the original scanner evidence.

| Research unit | Recorded count | Source |
| --- | ---: | --- |
| Final discovery case linkages | 3,809 | 29 Aug source and discovery run manifest |
| C1 scanner-opportunity positives | 192 | `matched_control_c1_v1_1/C1_SUMMARY.json` |
| C1 potential scanner-negative pool | 3,617 | Same C1 summary |
| C2 matched positive/control pairs | 190 | `matched_control_c2_v1_0/C2_SUMMARY.json` |
| C2 unmatched positives | 2 | Same C2 summary |
| C2 same-repository opportunity-superset pairs | 115 | Same C2 summary |
| C2 cross-repository exact-opportunity pairs | 75 | Same C2 summary |
| Phase1 producing changes | 455 | `broad_vuln_production_phase1_v1_0_49170/PHASE1_QC_SUMMARY.json` |
| Distinct eligible positive workflows in Phase1 | 191 | Same Phase1 QC |
| C/D code-decision roots | 342 | `D_COMPLETE_ROOT_PROVENANCE_v1_0/D01_INDEPENDENT_AUDIT.json` |

### Stage identity and why 198 is not 192

Read-only SELECT/GROUP BY queries against the *August 17 HF snapshot* and
the *later continuation database* each show 3,809 total cases, but:

| Snapshot | `needs_review` | `scanner_running` |
| --- | ---: | ---: |
| 17 August Hugging Face snapshot | 138 | 1,459 |
| Later 3,809-case continuation | 198 | 653 |

These snapshots are **not the final 29 August frozen study input**; they
remain un-hashed in the current independent reproducibility checkout. A
case-stage status or an unfiltered `downstream_signal='vulnerability'` count
must NOT be substituted for C1's final 192 scanner-positive set. The six-case
difference between continuation `needs_review=198` and final C1 `positive=192`
does not by itself tell us *which* cases changed, *why*, or whether every C1
positive was already included in the 198. Those questions require the exact
final database and frozen C1 membership.

### Scanner-opportunity and matching mechanics

C1's source audit reports a final-study DB hash matching
`126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`
and freezes positive-ID digest
`391a88c59dc73a356972ba0f4f3bb97892649c4df578784faccd195726cccf32`.
It defines **complete opportunity** as successful **base and head** for
CodeQL, OSV and Trivy; Gitleaks, Semgrep and dependency-diff require an
applicable successful single-stage run. Source-reported success codes are
`complete`, `completed`, `finding`, `ok`.
**C1 selects no controls**, and the original audit says it did not read
issue/PR text, manual annotations or scanner finding content.

C2 consumes the frozen C1 file with input SHA-256
`6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b`.
It selects controls *without replacement*, prioritizing maximum
cardinality, maximum Tier A pairs, and then minimum normalized distance
with deterministic seed `20260903`.
Tier A requires same repository and scanner-opportunity superset;
Tier B permits another repository only when scanner-opportunity signatures
match exactly. Its archived calipers include 90 days and approximate 4x
changes in lines/files. C2 intentionally conducts **no substantive
positive-versus-control outcome comparison**.

### From 455 producing changes to 342 roots

The Phase1 455-PC manifest declares a frozen provenance CSV SHA-256
`3435db03d6d03d7fe4c7799f949b20b2d7328cb8e718d8ba769174c54ddf50d6`.
Its Phase1 status is **REVIEW_REQUIRED**, and recorded introduction
classification remains **414 resolved + 41 unresolved**. Its finding-family
categories are **261 code vulnerability**, **96 dependency vulnerability**,
**64 dependency downgrade**, **26 secret exposure**, **8 dependency change**,
which sum to 455. The categories are **not 455 independently confirmed real
vulnerabilities**. Source reports 160 pilot + 295 scaleout contextualized
changes across 191 workflows.

The independent D0/D1 audit records this **root-size distribution**:

| Producing changes in one root | Number of roots |
| ---: | ---: |
| 1 | 283 |
| 2 | 36 |
| 3 | 9 |
| 4 | 7 |
| 5 | 3 |
| 6 | 3 |
| 12 | 1 |

The weighted total is exactly **455 changes** and **342 roots**.
The D audit records no duplicate assignments, cross-workflow roots or
root-count mismatches. This is a source-recorded, cross-stage consistency
test, not rerunning the annotators or validating root causal interpretation.

## Run the available read-only aggregate audit

From the root of the independent private Git repository:

~~~bash
python -m analysis.cluster_stage_lineage audit-recorded
python -m unittest tests.test_cluster_stage_lineage -v
~~~


The command requires exact known denominator and provenance relationships
and exits nonzero if the recorded summary drifts. It never accesses Wits,
Hugging Face, an external tool or any original case texts. The standard CI
pipeline runs it, but only as an **aggregate arithmetic gate**.

## Stronger future gate: verify original local C1/C2 CSVs byte-for-byte

Once two researcher-approved **private local copies** are accessible
outside the repository, run:

~~~bash
python -m analysis.cluster_stage_lineage verify-staged-c1-c2 \
  "/secure/local/C1_CASE_SCANNER_OPPORTUNITY_3809.csv" \
  "/secure/local/C2_MATCHED_PAIRS_FROZEN.csv"
~~~


The original sources/recorded digests are:

| Frozen local input | Expected SHA-256 | Original length |
| --- | --- | ---: |
| C1 case-opportunity CSV | `6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b` | 841,710 bytes |
| C2 matched pairs CSV | `4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b` | 56,175 bytes |

The future checker requires exact source SHA-256/byte lengths, unique C1
case IDs, precisely 192 positive C1 labels, precisely 190 positive/control
pairs, no re-used controls, 115 Tier A / 75 Tier B, matching repository and
scanner-opportunity memberships and the 90-day caliper. Its output contains
**only aggregate numbers**, never case IDs or private CSV rows. It refuses
symbolic links, files inside the Git checkout, changed files, malformed
rows and modified hashes. It does **not** rerun the original matching
optimizer or recalculate CodeQL findings from the final database.

**Both original CSVs have now passed independent read-only complete-file
SHA-256 checks in the research artifact store.** Their stored row-level
internal counts were audited separately, but the *combined per-case C1–C2
crosswalk* command has not been executed on both real files in one offline
session. Synthetic fixtures test that command's logic. Neither original
file is bundled with this Git PR.

## Still open

- Authenticate the actual Hugging Face private dataset revision and file
  byte SHA; the repo app/connector is not yet connected in this session.
- Independently recompute the final 192-case indicator from the final
  SHA-matched SQLite with its frozen C1 selection logic, not from early
  miner's `needs_review` status.
- Independently read/verify 455 original case→producing-change mappings and
  342 root assignments without losing D/D7 label differences.
- Recalculate the 190-pair matched-control analyses and uncertainty from
  the original per-pair coded outcome tables.
- Locate all 14 original O/W/P before-SARIF, reconcile their exact CodeQL
  version/pack and rerun introduced-warning attribution.

**These stages are not complete merely because stage totals reconcile.**

### Standalone frozen C1 and C2 artifact checks

Two independent commands now exist. `analysis.frozen_c1_cohort_gate` checks an original local C1 CSV against the **3,809-case / 192 stored-positive** fingerprint, without C2. `analysis.frozen_c2_pair_gate` checks C2's **190 existing pairs, 115 Tier A / 75 Tier B** with its original hash, without C1. They can be run before `analysis.cluster_stage_lineage verify-staged-c1-c2`, which checks the **cross-file memberships**. All real inputs must remain outside Git. **Direct full-file C1 and C2 SHA-256 verification has now passed**; cross-file C1–C2 case membership, historical positive-label correctness and the final SQLite remain open. These checks do **not** recalculate whether 192 labels represent true scanner-introduced vulnerabilities.

### New independent C1 source-byte audit

The original C1 file's 841,710 bytes matched source SHA-256 `6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b`, with **3,809 unique increasing case IDs, 192 stored positives and 3,617 stored negatives** and no invalid binary labels. The earlier C2 file was separately hash-verified. These are two independently recovered *frozen source artifact* identities; matching C1/C2 membership against each other and reconstructing 192 scanner positives from the final SQLite remain unverified. See `provenance/c1_cohort_readonly_audit_20261021.json` and `provenance/c2_pair_readonly_audit_20261021.json`.
