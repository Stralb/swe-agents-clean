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

Recovery of the original miner and experiment drivers is tracked in [the source-only recovery intake](docs/SOURCE_RECOVERY_STATUS_20261020.md). **1,075 historical source files from seven archives have been imported byte-for-byte** onto the separate `recovery/source-snapshots-20261020-235319-2ca255c5` branch. The reconstruction work branch `work/miner-core-consolidation-20261021` and [draft PR #1](https://github.com/Stralb/arno-research-reproducibility/pull/1) are based on that recovery branch. This work is **not merged into `main`**. Historical source imports are evidence preserved for audit, not automatically executable production modules. [`tools/verify_source_snapshot.py`](tools/verify_source_snapshot.py) verifies the source manifest.

## 21 October 2026 — work-branch scanner and worker validation

The work branch executes SHA-verified original AST definitions for collection, scanner recording, six scanner orchestration paths and original worker-job dispatch against **disposable, synthetic-only** SQLite databases. The exact historical pure dependency-diff implementation has now also been promoted byte-for-byte into active `src/scanners/dependency_diff.py`; `packaging==25.0` is provisionally pinned for its version-comparison semantics. Original OSV/Trivy pure advisory and change-target attribution methods and their exact top-level archived scanner drivers have separate SHA-pinned offline contracts. The full original OSV/Trivy Git snapshot construction and synthetic runner paths have passed a dedicated **11-test network-disabled container gate**, and **genuine OSV 2.6.0 and Trivy 0.76.1 are now separately integrated** with synthetic-only offline advisory data. OSV uses a fabricated one-record local DB; Trivy uses a SHA-256-verified immutable public advisory DB from 25 September 2026. The standard Python CI suite reports **454 tests: 442 passed and 12 intentionally skipped** (the opt-in genuine-executable tests run in separate OSV/Trivy, CodeQL, Gitleaks and Semgrep workflows). Dedicated release-checksum-verified smoke jobs exercise genuine Gitleaks 8.30.1 and Semgrep 1.181.0. Semgrep has also passed its two real-engine checks in a container with Docker `--network none`, a read-only repository and filesystem, dropped Linux capabilities, a non-root user, and disposable temp storage.

See [the local OSV/Trivy network-none validation](docs/MINER_OSV_TRIVY_NETWORK_NONE_GATE.md), [the original dependency-diff backend contract](docs/MINER_ORIGINAL_DEPENDENCY_DIFF_BACKEND.md), [OSV/Trivy attribution contracts](docs/MINER_OSV_TRIVY_ATTRIBUTION_PURE.md), and [the scanner execution and environment gate matrix](docs/MINER_SCANNER_RUNTIME_GATES_20261021.md) for precise evidence boundaries and open requirements. **These are technical reconstruction and synthetic smoke results, not reproduction of the historic 3,809-case pipeline, scanner-alert rates or the published statistical contrasts.** Original cluster data, the original study repo, historical file bytes and the default `main` branch have not been modified. The work PR stays draft pending source, environment and scientific release gates.

**Verified genuine CodeQL candidate:** [The isolated CodeQL v2.27.3 Python security-extended test passed](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39639711875), producing a genuine `py/command-line-injection` SARIF alert with CWE-078/CWE-088 on the fabricated changed line. Its exact original SHA-pinned base/head Git, database creation, SARIF interpretation, added-line attribution, archived worker and disposable SQLite path passed end to end in 64.5 seconds. The first attempt failed because a non-root container could not read bundled precompiled query plans, causing a 600-second baseline timeout; CI now fixes **permissions on the throwaway verified bundle only**, keeping the actual scan container read-only and network-disabled. No original CodeQL version/query-suite or historical SARIF baseline has been attested; [see the CodeQL gate contract](docs/MINER_REAL_CODEQL_PYTHON_GATE.md).

**Verified genuine dependency-scanner gate:** [OSV real offline Git+worker replay](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39623833532) passes 4/4 tests with an explicit fake advisory under Docker `--network none`. [Trivy immutable DB replay](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39623833418) passes 3/3 tests with a public September 2026 frozen OCI layer (SHA-256 `f834840e1109c7a3dc46244cf80bd00485a77a6a8ffe825fcd2aedbf22e5ec0d`) and real base/head findings carried through the archived worker and disposable SQLite. The Trivy advisory DB is intentionally **outdated for live vulnerability assessments**, and neither candidate scanner/database is documented as the original research environment. More information: [genuine scanner runtime contract](docs/MINER_REAL_DEPENDENCY_ENGINES_GATE.md) and [Trivy immutable DB gate](docs/MINER_REAL_TRIVY_FROZEN_DB_GATE.md).



## Frozen empirical-provenance replay

[The recorded-evidence gate](docs/FROZEN_EVIDENCE_REPLAY_GATES.md) validates
the existing O/W/P-14 arm counts, 12 truly paired cases, four provisional
snapshots, 39/40 JSX-aware syntax outcomes and 43 unresolved D/D7 root-label
conflicts directly from the frozen committed ledgers. CI runs the read-only
`python -m analysis.frozen_evidence_gate audit-recorded` command and synthetic
negative tests. This is **arithmetic/source-consistency replay**, *not*
independent reproduction of before/after CodeQL warnings. All **14 original
O/W/P before-SARIF** files are still absent from the available export, with
their expected hashes recorded; `verify-baselines` will exit 2 until
they are supplied separately as approved, local, read-only copies. The
original study's 3,809-workflow SQLite/database and full root/control
statistics still require their external frozen inputs.


## Byte-level protection for imported historical source

The [historical-source integrity gate](docs/IMPORTED_HISTORICAL_SOURCE_INTEGRITY.md)
rehashes all **1,075 originally imported historical files** (11,926,471 bytes)
against their frozen per-file source index on every normal CI run. It
also hash-verifies the **two separately recovered CodeQL evaluator scripts**
while never executing them; the one remaining unindexed `historical/README.md`
is documentation. Missing, modified, injected, symlinked or noncanonical
historical members block CI. This proves preserved code bytes inside Git,
**not** reproduction of the empirical database or research results.


## Original historical SQLite database: still blocked

[The read-only SQLite candidate intake](docs/FROZEN_SQLITE_CANDIDATE_INTAKE.md)
is now implemented and tested entirely on small synthetic copies. Its
checksummed, immutable SQLite mode never calls the original migration-capable
`Database` class and rejects live WAL sidecars or unapproved local
filenames. A passing *candidate* establishes only byte identity against
a private, self-reported manifest and structural integrity. It **does not**
reproduce the original 3,809 workflows, 192 scanner-positive workflows,
455 changes or 342 C roots. The actual historical SQLite bytes, its independently verified capture,
security-paper cohort-selection SQL, and original scanner revisions remain
**unrecovered**. The archived discovery source now supplies an **expected**
database SHA-256 and the exact 3,809-case linkage SQL; see the
[source-only discovery lineage](docs/FROZEN_DISCOVERY_DB_LINEAGE.md).
The blocker is explicitly registered in
`provenance/frozen_database_recovery_status.json`.

### Located source, integrity not yet attested

A read-only Wits cluster check recovered the **actual final-study SQLite
path** and a matching **source+run-manifest SHA-256 expectation**. The user
reports that the freeze also lives at the private Hugging Face dataset
`Stralb/malicious-issue-miner-data`, under
`final/full3809-scanner-complete-20260829`. Earlier August 17 and later
continuation SQLite snapshots were queried read-only and each contained
3,809 cases, but those are separate versions. The actual final DB contents,
Hugging Face revision, and final-file hash are **not yet independently
verified**. The data must remain outside Git. See
[database location and provenance](docs/FROZEN_DISCOVERY_DB_LINEAGE.md).


## Frozen positive cohort to matched controls and C/D decision roots

The [cluster study-stage evidence ledger](docs/FROZEN_COHORT_STAGE_LINEAGE.md)
records and arithmetically checks the original **192/3,617 C1
positive/negative partition**, **190 matched pairs (115 same-repo, 75
cross-repo)**, **455 producing-change records in 191 positive workflows**,
and **342 separate decision roots**. These totals are grounded in cluster
C1/C2/Phase1/C/D frozen summary manifests, with their source paths,
cross-stage input hashes and synthetic negative tests. Two *earlier* 3,809
case snapshots have `needs_review` counts **138** and **198**, confirming
that operational status is **not interchangeable** with final C1's **192**.
The original Phase1 evidence records **414 resolved and 41 unresolved**
introduction assessments, so the 455 are not 455 independently proven
vulnerabilities. Recorded-stage arithmetic is now supplemented by independent full-file
SHA-256 and stored-row audits of the original C1 and C2 CSVs. The
**case-by-case C1–C2 crosswalk** later passed a full original-row internal consistency audit; final SQLite regeneration, independent scanner outcomes and causal experiments remain open. An optional **local-only**
hash-locked C1/C2 membership verifier is ready; no confidential CSV files
were copied into Git.

### Standalone frozen C1 and C2 artifact checks

Two independent commands now exist. `analysis.frozen_c1_cohort_gate` checks an original local C1 CSV against the **3,809-case / 192 stored-positive** fingerprint, without C2. `analysis.frozen_c2_pair_gate` checks C2's **190 existing pairs, 115 Tier A / 75 Tier B** with its original hash, without C1. They can be run before `analysis.cluster_stage_lineage verify-staged-c1-c2`, which checks the **cross-file memberships**. All real inputs must remain outside Git. **Both original C1 and C2 file SHA-256 digests have now been verified against their frozen manifests**; independent C1–C2 member comparisons and the final historical SQLite remain open. These checks do **not** recalculate whether 192 labels represent true scanner-introduced vulnerabilities.

The independent C1 byte audit records exactly **841,710 original bytes**, **3,809 strictly ordered unique case IDs**, and **192 stored positive / 3,617 stored negative labels**, with an exact recorded source SHA match. No private C1 CSV rows were committed; see [the audit record](provenance/c1_cohort_readonly_audit_20261021.json). This verifies a frozen input artifact, **not** the correctness of its original vulnerability labels.


## 22 October 2026 — live C1/C2 source crosswalk, binary C6 sensitivity and D7 route flag

An additional **read-only Wits DCR audit** independently cross-checked every one of the **3,809 C1 records** against the frozen C2 pairing and corresponding original control/positive fields: **190 pairs (380 matched case records), zero cross-file inconsistencies**, with 115 same-repo and 75 cross-repo pairs. The unchanged original CSV SHA expectations were attested separately in earlier evidence; the final 29 August SQLite still has no independently authenticated copy. See [the C1/C2 and scalar C6 audit](docs/C1_C2_LIVE_CROSSWALK_AND_C6_SCALAR_REPLAY_20261022.md).

Two more frozen primary comparisons were independently **mathematically matched using case-level pairing plus the later continuation SQLite**: same issue/PR author (exact McNemar p=1.000) and issue-to-PR delay (paired Wilcoxon p≈0.24123). With the earlier five **indexed-aggregate** omnibus reconstructions, seven of the nine primary comparisons have computational checks, **not all at the same provenance level**.

The original C6 control-context CSV was inspected directly: **human reviews 47 Yes of 189 complete controls (one failed API response)**; **any prior repository activity 140 Yes of 187 complete controls (three failed API/search responses)**. These independently observed control margins reconcile with the preserved rates and give **conditional**, not raw-pair-verified, exact binary McNemar reconstructions: human review p≈0.418754 and prior activity p≈0.335558. The archived catalog says N=190 for prior activity, whereas the source percentages and control missingness indicate N=187 complete cases; **do not silently replace the old sample-size field without authenticating the original C6 master**. See [the missingness/reconstruction audit](docs/C6_BINARY_CONTROL_MISSINGNESS_CONDITIONAL_REPLAY_20261022.md) and the [read-only conditional arithmetic tool](analysis/c6_binary_conditional_gate.py).

A candidate SQLite chronology audit found **nine matched pairs** where at least one linked issue was created after its PR. An [exhaustive adversarial deletion analysis](docs/C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) of indexed C6 binary matched counts proves that *removing any nine of the 190 pairs* cannot reverse the effect direction of explicit instructions, suggests-solution, or aligned goal; their separate worst-case exact binary McNemar p-values are **0.032766, 0.013531 and 0.006611**. These are **post-hoc category sensitivity bounds**, not regenerated historical Stuart–Maxwell omnibus significance, formal multiplicity-adjusted results, or an actual nine-row restricted-sample analysis. Re-run with `python -m analysis.c6_chronology_deletion_bounds --remove-pairs 9`.

A focused [D/D7 route-conflict audit](docs/D7_CROOT_00649_RELOCATION_ROUTE_AUDIT_20261022.md) compared the genuine base/head GitHub code for CROOT-00649-01. Five Windows sanitizer replacement operations were **textually identical** before/after migration into a shared module. The later continuation database records five `js/incomplete-sanitization` findings at the new file, with the same primary location fingerprint and distinct end lines. **No original base SARIF was verified**, so this signals a plausible inherited-code relocation / scanner-warning-vs-vulnerability attribution threat, **not** a proven false positive or adjudicated route. The D-final M/T1 vs D7 H/NA disagreement and all 42 other tier disagreements remain unresolved; 17 of the 43 involve an INCOMPLETE tier.

The [43-disagreement triage](docs/D7_43_DISAGREEMENT_TRIAGE_20261022.md) groups unresolved labels into **34 workflow-level evidence dossiers**, with **10 dossiers covering all 17 incomplete-tier roots**; this is triage, not adjudication.

The private draft PR remains **unmerged**. Synthetic/aggregate-only unit tests and integrity checks are automatically executed by GitHub Actions; a workflow passing does **not** attest the missing original C6 paired labels, final SQLite, 14 O/W/P before-SARIF files or causal counterfactual outcomes. Original cluster files and jobs were not modified.


## 22 October 2026 — live chronology, task-scope and CodeQL overlap follow-up

An independent read-only [four-case issue-after-PR audit](docs/FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md) crossed original Wits D1/D2 root-evidence packets with publicly accessible GitHub issue and PR file changes. **Four scanner-positive workflows whose issues were created after their PRs account for 14 of the 342 mechanism roots and 8 of the 43 unresolved D/D7 differences**. Two of those mixed-task PRs (cases 5264 and 5267) contain **12 roots from a broader feature distinct from the later linked issue's specific requested fix**. Case 5267, for example, fixes a migration bug in a follow-up commit but its seven security-producing roots all concern an independent version-preview feature. The two remaining cases have different issue-to-root relationships, so no blanket exclusion or historical relabeling was performed. The accompanying [fail-closed aggregate ledger](provenance/late_issue_four_positive_root_scope_20261022.json) and [scope-audit checker](analysis/late_issue_root_scope_gate.py) enforce evidence/provenance boundaries; the frozen D/D7 disagreement list is unchanged.

This is a **new, high-priority construct-validity and source chronology gate**: a PR closing an issue does not prove that issue covered every scanner-producing root, let alone served as the agent's earlier instruction. Subsequent C6 and mechanistic/causal claims require root-level issue coverage and as-of-implementation issue snapshots before reclassification. The previously documented [worst-case nine-pair C6 binary exclusion bounds](docs/C6_CHRONOLOGY_NINE_PAIR_ADVERSARIAL_BOUNDS_20261022.md) do not establish actual restricted-sample Stuart–Maxwell tests or causal influence. A new [exhaustive nine-pair original-multicategory Stuart–Maxwell sensitivity](docs/C6_EXHAUSTIVE_OMNIBUS_NINE_PAIR_BOUNDS_20261022.md) now enumerates **8,006** feasible instruction-specificity table exclusions (maximum full-rank p≈**0.01927**) and **2,788** feasible goal-alignment exclusions (**2,136** full-rank, maximum p≈**0.03934**; **652** delete the rare 'Unclear' class and make the *original* fixed-class test singular). A separately specified rank-adaptive sensitivity bounds those 652 at maximum p≈**0.01684**, but it is **not** the historical method. All results are **nominal, indexed-aggregate, noncausal** bounds, not actual case-level omnibus recomputations or nine-family Holm robustness.

A separate read-only [CodeQL fingerprint-overlap audit](docs/CODEQL_CANDIDATE_LOCATION_OVERLAP_AND_SARIF_EXCLUSION_20261022.md) checks the *later continuation* SQLite: **392 introduced CodeQL scanner rows across 131 cases**, **385 groups by case/rule/file/line hash**, and **388 groups when adding start-column fingerprint and message**. Only **one** refined group recurs (five case-649 raw findings with different end lines); none were deduplicated or declared separate defects without original SARIF. A superficially matching **S5PAIR-025** old calibration-before SARIF was read in full and hash-tested, but its digest and result count **do not match** the expected original O/W/P baseline for case 03581. The **14 original O/W/P before-SARIF files therefore remain unverified**.

The original Wits directories, Slurm jobs, third-party repositories, historically coded roots, and frozen C6 data were not changed; the engineering branch remains draft and unmerged.


## 22 October 2026 — complete full-cohort issue/PR event chronology

The additional [full-cohort chronology audit](docs/FULL3809_ISSUE_PR_CREATION_CHRONOLOGY_20261022.md) joined the **3,809 original frozen C1 case memberships** to PR/issue timestamps from the later (non-final, unauthenticated) Wits continuation SQLite. **49 linked issues** were created **after the associated PR opened** (**4/192 scanner-positive, 45/3,617 scanner-negative**); **five** of those issues were not created until **after the PR already merged**, and all five are C1 scanner-negative. This is a timestamp/construct-validity limitation, not a reconstruction of every case's true task prompt. Original C1 memberships were independently read from all 841,710 bytes in three non-overlapping source-byte segments, recovering **3,809 rows and all 192 stored positive flags** without changing data. Original C2's 190 matched pairs were then reread completely and checked against all 49 late-issue IDs, confirming **nine affected pairs, four positive-side late issues, six control-side late issues and one pair affected on both sides**.

The [fail-closed full-cohort chronology checker](analysis/full3809_event_order_gate.py), [synthetic/recorded-ledger tests](tests/test_full3809_event_order_gate.py), and [small source-indexed metadata ledger](provenance/full3809_issue_pr_event_order_20261022.json) deliberately *do not* certify the final 29 August SQLite file, historical issue-text snapshots, root-to-issue causal assignments or original C6 raw paired tests. They verify reproducible arithmetic and source membership only. **Five after-merge issues could not have instructed their earlier merged PRs**, whereas issues created after PR opening but before merge might still have informed later issue-specific commits. Treat each workstream and scanner-producing root separately before using an issue as a causal/interpretive explanatory variable.

The complete current positive-side [four-case task-scope audit](docs/FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md) remains exploratory; frozen labels and all original cluster files remain unchanged. The draft PR remains **unmerged** pending full-source and scientific release gates.


## 23 October 2026 — whole-cohort issue chronology and root-level coverage gate

The [read-only C1/C2 chronology census](docs/ISSUE_PR_CHRONOLOGY_WHOLE_COHORT_20261023.md) matches **all 49 issue-after-PR-creation case IDs** in the later continuation SQLite against the complete original C1 scanner-positive/negative population (4 positive, 45 negative); **five linked issues were created only after PR merge**, all C1 negative. The 190-pair frozen C2 CSV contains **nine affected pairs** (four Tier A, five Tier B; four positive-side and six control-side late issues, with one pair late on both sides). The [provenance ledger](provenance/c1_c2_late_issue_chronology_census_20261023.json) preserves case IDs only; the [source-gated verifier](analysis/c1_c2_late_issue_chronology_gate.py) can SHA-check approved original C1 and C2 CSV bytes before independent paired membership verification. Source hashes were separately attested in earlier recovery, but were **not recomputed during this particular census**, and the source SQLite is still **not** the hash-authenticated final August 29 database.

A new [issue-to-root relevance and chronology codebook](docs/PROPOSED_ISSUE_TO_ROOT_COVERAGE_CODEBOOK_20261023.md) is explicitly **proposed, not frozen or executed**. It separates mere GitHub issue↔PR linkage from issue availability at the root commit and task-level coverage, using independent blind coding and explicit missing evidence. Source-specific mismatches in cases 5264 and 5267 establish the need for this distinction; they do **not** authorize reclassification of the original 342 roots, 43 D/D7 disputes, or C6 nine-primary results.

The separate original multi-category C6 omnibus chronology deletion bound is documented in [its research module](analysis/c6_omnibus_chronology_deletion_bounds.py); its maximum fixed-category nine-pair-deletion goal-alignment p-value is **0.03933869747965109** (chi-square exactly **1127/135**, df=3). An earlier test fixture's 0.03933883034619607 was a wrong reference, independently corrected against exact rational arithmetic, SciPy and high-precision gamma. This is a **post-hoc indexed-aggregate robustness analysis**, not a reexecution of original paired C6 raw bytes or a familywise-corrected result.


## 23 October 2026 — D-final / D7 version-stability measurement

The [pinned D/D7 ledger stability audit](docs/D7_LABEL_FAMILY_STABILITY_SENSITIVITY_20261023.md) and [source-hash-checked analysis module](analysis/d7_label_stability_gate.py) independently count the **43 unresolved differences** without selecting a canonical label. **Only 1/342 top-level H/T/M routes differs**, whereas **42/233 explanation tiers among roots assigned M in both versions differ**; **17** tier disputes involve `INCOMPLETE`. Among the disputed roots, D-final assigns **16** to direct reuse (T1) and D7 only **3**: a net **13-root subtype sensitivity** hidden by apparently stable coarse routes. Original full 342-root D/D7 files and adjudication logs are **not** authenticated, so the 299/342 exact agreement computation assumes the difference-only ledger is exhaustive. These versions are not independent coders; do not claim inter-rater reliability, adjudication or causal validity. The private research PR remains draft/unmerged and all Wits originals unchanged.


## 23 October 2026 — original Wits D evidence index byte-authenticated

The complete **47,826-byte** original Wits `D_EVIDENCE_INDEX_342.csv` has now been independently reassembled via read-only AServerV6 and **SHA-256 matched** to the archival `SHA256SUMS.txt` (`cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6`). This new [source-authenticated evidence-channel audit](docs/D_EXPORT_SHA_AUTHENTICATED_D7_CHANNEL_CROSSWALK_20261023.md) joins all 342 original evidence-index roots to the frozen 43-row D/D7 difference ledger. **None** of the 43 disputes is marked export-chronology `INCOMPLETE`; **18** are `URLS_PRESENT_UNFETCHED`. All **17** disputed semantic `INCOMPLETE` tiers have exporter chronology `COMPLETE`, and **11 of those 17** have external guidance `NOT_APPLICABLE`, including the **four** contested D-final T5→D7 INCOMPLETE roots in workflow 05267. This **does not adjudicate** any root or establish that the codebook's full evidence-sufficiency test was met. Conversely, **41 original roots with exporter chronology `INCOMPLETE` lie outside the 43 known differences**, requiring label screening once complete original D/A/B adjudication files are recovered.

The Wits v1.1 deterministic evidence export was recorded `PASS` but explicitly performed **no semantic classification**. Earlier, separate D21 enrichment and D3 build stages contain scoped failure markers; the available coder/adjudication result directories do not independently authenticate final semantic labels. The [fail-closed channel projection checker](analysis/d7_evidence_export_channel_gate.py), [tests](tests/test_d7_evidence_export_channel_gate.py), [derived private provenance](provenance/d7_original_evidence_export_channel_crosswalk_20261023.json) and scientific [P-038 blocker](provenance/OPEN_ISSUES.md) retain this distinction. All original Wits data and historical D/D7 labels remain unchanged.


## 23 October 2026 — 41 chronology-incomplete roots traced to npm lockfile

A new original-source [41-root audit](docs/D_41_CHRONOLOGY_INCOMPLETE_LOCKFILE_ROOTS_20261023.md) narrows the `channel_chronology=INCOMPLETE` source-export gap: **all 41 roots** across **six positive workflows** are **one-PC npm `package-lock.json` dependency-version findings**, not 41 independent workflows. **Thirty-six (87.8%) belong to case 13918**, which the separately source-verified [C1/C2 crosswalk](docs/C1_C2_CROSSFILE_RECONCILIATION_20261022.md) establishes was **one of the two unmatched positives** excluded from the 190-pair C6 design. The complete original **66,543-byte D1 root index** was now **reassembled from binary Wits chunks and independently SHA-256 matched** to its original recorded digest. A targeted read of the original C6 root census confirms the 36 root boundaries each have `PC Count=1`, `Merge Rationale=singleton PC`, and `Final Source=A_B_AGREEMENT`; source-side root construction agreement is **not** proof of independently selected security mechanisms or semantic D-route adjudication. The public [issue #172](https://github.com/Pimzino/spec-workflow-mcp/issues/172) and [PR #173](https://github.com/Pimzino/spec-workflow-mcp/pull/173) show a real approvals fix alongside a **10,451-changed-line package-lock update**.

The [source-pinned aggregate ledger](provenance/d_chronology_incomplete_41_lockfile_census_20261023.json), [fail-closed staged-source checker](analysis/d_chronology_lockfile_concentration_gate.py), and [unit tests](tests/test_d_chronology_lockfile_concentration_gate.py) preserve the complete frozen 342-root denominator and never assign H/T/M from file type alone. The 41 exporter-incomplete flags do **not** overlap any of the 43 known D-final/D7 semantic disagreements. Original full D route/tier labels, npm resolver decisions, historical scanner validity and original-source final database authentication remain unverified; all data/label/code changes were confined to this private **draft PR**, with Wits read-only.


## 23 October 2026 — post-merge advisory publication: retrospective warning versus prospective knowledge

A targeted [seven-advisory temporal-validity audit](docs/RETROSPECTIVE_DEPENDENCY_ADVISORY_TEMPORAL_VALIDITY_20261023.md) combines original Wits D2 source packets, read-only actual GitHub PR merged timestamps and upstream/GitHub-reviewed advisory publication dates. **Seven distinct original D1 roots from six workflows** have named GHSA advisories published **3–176 UTC calendar days after the associated PR merged**. Five distinct workflows were included in the original 190 positive-control pairs, while case 13918 supplies **two** observations and is the original source-verified **unmatched positive**. The seven advisory dates were reviewed **individually** and are *not* a full 41-root or 190-pair advisory census.

**Science scope:** Modern scanners may correctly find a retrospectively vulnerable dependency even where the specifically named warning was not publicly published at task time. This does **not** establish that the vulnerability did not exist earlier or that no private disclosure/alternative guidance was available. Retrospective future-warning insertion is a **hindsight-oracle counterfactual**, not a deployable pre-PR warning retrieval method. The [seven-source/date ledger](provenance/seven_postmerge_advisory_publication_cases_20261023.json), [cross-source fail-closed audit](analysis/seven_advisory_temporal_replay_gate.py), [tests](tests/test_seven_advisory_temporal_replay_gate.py), and [P-040 open release gate](provenance/OPEN_ISSUES.md) all preserve that distinction. No historical datasets, scanner results, classifications or cluster jobs were changed.


## 23 October 2026 — all 36 source D2 packet hashes, 131 findings and adversarial outlier bounds

The [full 36-root source census](docs/CASE13918_D2_ORIGINAL_36_ROOT_131_FINDING_CENSUS_20261023.md) independently reads all **36 original D2 evidence packets** for case 13918 and records the complete **one-chunk-per-original-file source-reported SHA-256** and byte lengths (**319,315 original D2 bytes**), with optional external local independent re-SHA. The exact source mapping contains **131 unique original canonical scanner finding IDs `CF-0929`–`CF-1059`**, despite only **36 one-PC package-version roots and one merged workflow**. The two largest roots contribute **51 findings (38.9%)**. Ten identical source CVE identifiers recur across paired versions of `fast-uri`, `minimatch` and `picomatch`, demonstrating that **distinct CF records are not necessarily distinct vulnerabilities**. The three source-referenced CVE-2025 advisories (`ajv`, `lodash-es`, `qs`) all have a specific public GHSA publication date **after** the historical December 2025 PR merge; a CVE ID's year is **not** a proof of publication timing. Exhaustive advisory-date coverage and vulnerability reachability are still open. Case 13918 was excluded by the original **C2 deterministic caliper matching**, so this concentrated PR contributes none of its original 36 roots directly to the historical **190 C6 matched pairs**.

The [provenance ledger](provenance/case13918_original_D2_36_packets_131_findings_20261023.json), [SHA/source-membership gate](analysis/case13918_d2_131_finding_source_gate.py) and [tests](tests/test_case13918_d2_131_finding_source_gate.py) keep scanner findings, producing changes, root decisions, workflows and unique-vulnerability claims separate. A distinct [exact adversarial outlier-prevalence bound](analysis/d_lockfile_outlier_prevalence_bounds.py) proves that the **source-reported root-level M majority** remains **above 63.7%** when any 36 or all 41 exporter-chronology-incomplete roots are hypothetically excluded under either D-final or D7 totals. This is *not* a confidence interval, a valid source-informed route adjudication, a C6 paired rerun or a scientific decision to drop original records; it is a nonparametric worst-case arithmetic sensitivity. The complete original D routes, warning-time catalogs, historical scanner baselines and final SQLite remain separate release blockers ([P-041](provenance/OPEN_ISSUES.md)).

**All original Wits data and existing frozen scientific labels remain untouched.**


## 23 October 2026 — original D2 packet archive complete; chronology flags differ by stage

[Read the new original-source stage audit](docs/D2_ORIGINAL_PACKET_ARCHIVE_TEMPORAL_STAGE_GAP_20261023.md). The Wits **35,656-byte** D2 packet index is now independently SHA-256 authenticated against the contemporaneous archived **63,478-byte** D2 `SHA256SUMS.txt` file. The archive contains exactly **342 coder-A original-root evidence packet path hashes, 342 blinded coder-B evidence packet path hashes and six control artifacts**, and every root ID/alias in the D2 index matches a manifest path. This **does not** recover or authenticate the final D route/tier classification outputs; the source archive contains **input evidence**, not completed H/T/M or T1–T5 coding.

**Temporal validity:** the original D2 index has **0/342 `explicit_chronology_fields_available=True`** despite **342/342** for seven generic evidence fields and **18/342** for explicit Phase-7 correction evidence. The later v1.1 D evidence export instead reports **301/342 `chronology=COMPLETE`** and 41 incomplete; these stage-specific fields **cannot be equated**. Only **6/43** unresolved D-final/D7 label differences overlap the original 18 D2 Phase-7 correction flags. The later export's actual guidance requires individual `eligible_prechange=YES` evidence before explaining a root implementation choice, and the exporter explicitly performs **no semantic classification**. This is an empirical source-provenance separation, **not** a conclusion that no temporal information existed, that the 301 complete statuses are wrong, or that any historical D labels were adjudicated.

The [source-locked provenance crosswalk](provenance/d2_packet_index_342_archived_stage_coverage_20261023.json), [optional raw-byte replay gate](analysis/d2_packet_index_archival_stage_gate.py), [unit tests](tests/test_d2_packet_index_archival_stage_gate.py) and [P-042](provenance/OPEN_ISSUES.md) retain original exact checksum identities and strict prospective-evidence nonclaims. All Wits originals and frozen research labels remain unchanged.


## 23 October 2026 — case 154 exact source-line chronology reverses the exported issue eligibility

A newly authenticated **root-specific source-order counterexample** requires special care in the prospective-issue claims. The original [Wits case154 D2 packet](provenance/case154_original_anchor_vs_target_line_timeline_20261023.json) is byte-level SHA-256 matched to the historical D2 exporter manifest. The complete leading **79,159-byte** original Pass-A evidence item for this root claims a high-confidence `cumulative_diff_anchor` introduction at **02:38:57 UTC** on 4 November 2025, and marks the issue created at **02:39:26** as `eligible_prechange=NO`. **Direct public GitHub file snapshots and contiguous commit comparisons contradict that exact-root chronology:** the scanner-targeted `phpTagRegex` does not exist at 02:38:57 nor at 02:45:52; it appears in commit [`8af3a292`](https://github.com/CAPHTECH/kiri/commit/8af3a292202668f2d3e254fee60cc959a7c126dd) at **02:55:56 UTC**, **16 minutes 30 seconds after issue creation**. The original source timeline was **16 minutes 59 seconds too early** for the target line. The earlier conclusion that this issue postdated its scanner-producing root was **retracted**; the original `NO` eligibility needs separate source-aware reassessment, **not an unearned conversion to YES** without proof of the issue-body version and agent's instruction receipt. Case 154 is among the original **190 C2 matched positives**.

See the [adversarial original-source chronology report](docs/CASE154_FALSE_EARLY_ROOT_INTRO_ANCHOR_20261023.md), [immutable five-commit source ledger](provenance/case154_original_anchor_vs_target_line_timeline_20261023.json), [read-only Git replay checker](analysis/case154_root_introduction_timing_gate.py), [tests](tests/test_case154_root_introduction_timing_gate.py) and [P-043 release gate](provenance/OPEN_ISSUES.md). **No cohort-wide failure rate is established** by this one root; a full audit must target *scanner-primary lines/mechanisms in their first actual PR commit*, not assume `cumulative_diff_anchor` equals root introduction. All original research datasets and D labels remain unchanged.


## 23 October 2026 — original Pass-A temporal-eligibility auditor and release-readiness estimate

A new [342-root offline original-source chronology audit protocol](docs/D_PASS_A_342_ROOT_TEMPORAL_ELIGIBILITY_AUDIT_PROTOCOL_20261023.md) builds on the verified [case-154 target-line attribution failure](docs/CASE154_FALSE_EARLY_ROOT_INTRO_ANCHOR_20261023.md). Its [read-only parser](analysis/d_pass_a_chronology_cohort_audit.py) pins the **25,549,416-byte** original Pass-A v1.1 JSONL exporter SHA-256 `4510cd4dacf218c918b82d4dfde4afefee270ba5b147a5558e7dbe87e486e8c0`; its [19 synthetic tests](tests/test_d_pass_a_chronology_cohort_audit.py) check complete/incomplete source-channel status, `YES/NO/UNKNOWN/N/A` item eligibility, multiple-PC and unresolved anchors, issue creation after PR, and fail-closed raw source mismatch. The original 342-root file is **not available as staged approved raw bytes in GitHub CI**: **a full original-cohort temporal replay has NOT been performed**. The existing complete Wits first case154 Pass-A item is a source-specific counterexample, not a prevalence estimate. Wits original files, jobs and all H/T/M labels were left unchanged.

For planning rather than scientific verification, see [the current completion and 14-gate scorecard](docs/RESEARCH_RECOVERY_COMPLETION_SCORECARD_20261023.md): **~90% recovery engineering**, **~65% scientific/source validation**, **~75% combined** at a declared 40%/60% engineering/science weighting. These are *subjective planning estimates* and **not** a measured share of historical evidence reproduced or a claim of publication readiness. Outstanding essential blockers remain complete D-final/D7 semantic outputs and 43 disagreements, original C6 190-pair master and four further primary replays, frozen scanner/CodeQL bases and database, and exact root-introduction/advisory chronology.
