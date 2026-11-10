# Open Scientific and Engineering Reconciliation Items

Every unresolved item must be closed by a reproducible artifact or accompanied by a limitation statement. The list is not an assertion that one candidate version is defective.

| ID | Question / disagreement | Required evidence | Current disposition |
| --- | --- | --- | --- |
| P-001 | D-final: H=5, T=103, M=234 versus D7: H=6, T=103, M=233; 43 label rows differ | Frozen D5/D7 CSVs; D4 adjudication; D7 correction ledger or script showing exact transformation and provenance | **BLOCKED — DO NOT SELECT CANONICAL LABELS** |
| P-002 | Which exact database and SQL define 3,809 workflow / 192 scanner-positive / 191 mapped workflows / 455 PCs? | Frozen DB SHA-256, source query, versioned scanner run and exclusion list | Unverified regeneration |
| P-003 | v2.1 is marked complete, but its own v2.2 failure audit flags generic/state patterns and parser artifacts | v2.2 full results, methodological precommitment and operation-level quality audit | v2.1 completed but scientifically limited; v2.2 execution incomplete |
| P-004 | Only three Git commits are visible in the live miner while many post-commit backups exist | Live files with SHA, backup classifications, associated tests, Slurm logs | Version lineage incomplete |
| P-005 | August 19 review-UI snapshot includes modules not included in the live miner | Pairwise file diffs and UI tests | No source promotion yet |
| P-006 | October warning-specific intervention may leak historical outcomes to generation | Original issue snapshots, W/P/O packet-building scripts, model transcripts, prespecified evaluator | Retrospective/oracle study, not prospective prevention |
| P-007 | Some recent cases do not reproduce historical scanner target; functions may not be tested | Paired CodeQL baselines, scanner version/queries, SARIF, tests, reproduction gate by case | Exploratory; do not claim prevention |
| P-008 | Outcomes for blind coding passes need fully documented independence and adjudication | Prompt/alias/crosswalk manifests, frozen Pass-A and Pass-B, adjudication timeline | LLM repeated passes; no human interrater reliability claim |
| P-009 | Full original 122-case, F1–F5 and NEW70 provenance not yet independently regenerated here | Frozen source data, codebooks, case-level QC, pipeline code and executed outputs | Historical, pending integration |
| P-010 | Repository licensing and permissible redistribution of external repo snapshots | Research permissions and third-party repository licences | Private staging only; no unreviewed redistribution |

## D versus D7 exact conflict

The original datasets contain identical root identifiers and producing-change memberships. Relative to D-final, D7 changes 43 final tiers; one of those also changes production route: **CROOT-00649-01, M/T1 → H/NA**. The original D archive reports 234 M roots, while D7 reports 233 M roots. See `d_vs_d7_label_differences.csv` for all 43 row-level transitions. This register does not choose which is canonical.

## Newly identified live-source concern

**P-011:** `src/distributed/local_coordinator.py` in the live export chooses the shared continuation database as its write target rather than the separately named working database in the August archives. This code must not be executed against original frozen datasets until a read-only reproduction copy and single-writer invariant are documented.

## Historical Phase 2 CodeQL evaluators (20 October 2026)

**P-012 — Scanner attribution semantics:** The original Phase 2 evaluator converts an unmatched but unchanged-location finding into `target_introduced=NO`; the revised evaluator instead reports `REVIEW`. Both rely on SARIF fingerprints and first-location changed-line overlap. Require original SARIF, exact query hashes, functional tests and manual data-flow attribution before interpreting `YES` or `NO` as causal security findings. See `docs/PHASE2_EVALUATOR_AUDIT_20261020.md`.

**P-013 — Destructive historical evaluation and stale checkpoints:** Neither script may be run on Wits as-is. Both remove existing working directories, the v1 also unlinks SARIF, and v2 can reuse checkpoints/SARIF without verifying current source/query/tool inputs. The `--preflight` flag still modifies the filesystem. A new create-only design and input-bound checkpoint validation are required.

**P-014 — Six-run O pilot versus October O/W/P:** Recovered `evaluate_phase2.py` and `phase2_eval_v2.py` cover only cases 3504, 10819 and 629 with two O runs each. Locate and audit the distinct 14-case O/W/P generation, CodeQL and functional evaluators before making October claims.

## O/W/P 14-case scanner and functional intake (20 October 2026)

**P-015 — Missing baseline SARIF:** The October CodeQL ZIP carries 40 after-scan SARIF files with verified result counts and patch hashes, but **none of the 14 baseline SARIF files**. All new/introduced alert classifications are therefore currently source-reported rather than independently recomputed. Recover the baseline SARIF by the archived `baseline_sarif_sha256` hashes before calling the comparison independently replicated.

**P-016 — Paired source equivalence:** For every one of the 14 cases, O/W/P (or W/P) records share the same *baseline SARIF hash*, but their `frozen_source_sha256` compressed-source byte hashes differ. The intake reports `frozen_repo_equal=true`, which we have not independently regenerated from the underlying repos. Verify source-tree content-level equivalence before comparing intervention arms.

**P-017 — Functional acceptance and syntax:** The 40 O/W/P syntax checks have an initial 37/40 pass rate, corrected to 39/40 by a JSX-aware parse. Case `16633-O` remains syntax-invalid due to a duplicate TypeScript declaration, despite zero source-reported new CodeQL alerts. Four passing standalone subcomponent checks do **not** establish full original-issue acceptance or functional equivalence.

**P-018 — Cohort provenance and confounding:** The archived comparison has 12 three-arm-paired cases (two missing O), four `FILTERED_SOURCE_PROVISIONAL` cases, eight previously reproduced precise target rules, and explicitly unverified as-of-PR issue provenance and generation-cohort comparability. Treat count differences as exploratory observations, **not** causal safety effects. See `docs/OWP14_EVIDENCE_AUDIT_20261020.md`.

## October O/W/P generator packets and patch-byte lineage (20 October 2026)

**P-019 — Complete coding-agent session provenance missing:** The `07_AGENT_PROMPTS_AND_TRACES.zip` export contains 41 Python scripts, 63 Slurm scripts, and 496 `.out`/`.err` logs, but no full per-generation coding-agent transcript/response metadata. The frozen packet constructor documents the intended prompt but not the actual models, randomness, independent fresh sessions or historical-issue-as-of-PR text. Retain O/W/P as exploratory until exact inputs, model/settings and session traces are recovered.

**P-020 — Safety property still oracle-informed:** W explicitly injects the historical CodeQL rule+diagnostic. P omits the rule ID but includes a case-tailored property selected from the historical failure mechanism. This is **not** a prospectively derived safety requirement and cannot demonstrate deployable warning prevention. Case 00668 uses packets copied from a previous freeze; do not substitute the later template without checking its original packet bytes.

**P-021 — Patch scope confounding:** In 12 three-arm-paired cases, W patches are smaller than O in 9/12 by bytes and 10/12 by changed lines; P is smaller in 9/12 by bytes and 7/12 by changed lines. Case 06104 has O=693 versus W=72 and P=100 added/deleted lines. Evaluate task completion and patch scope before treating lower CodeQL alert counts as safer outcomes. See `docs/OWP14_PATCH_AND_GENERATION_LINEAGE_AUDIT_20261020.md`.

**P-022 — Baseline SARIF files and source-base parity:** All 40 patch SHA-256 digests now match original transfer archives, preflight metadata, and scanner records. The 14 original `screen65_codeql_job70675/CASE_XXXXX/before.sarif` files remain missing, and underlying source-tree content equivalence across O/W/P packets has not been independently verified. Hash-verify both before recomputing new-alert deltas.

**P-023 — Historical driver correction sequence:** Of 41 archived Python job drivers, `owp14_20261018_v4/eval_668_uploaded_scannerfix.py` has a syntax error at line 101; `v4b` fixes it. Earlier P scan driver versions refer to a superseded preflight path and an absent sort field. Preserve the revision record and do not promote such runners without isolated tests.
