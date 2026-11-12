# Arno research: full historical evidence recovery checkpoint (25 October 2026)

**Status:** original evidence recovery in progress, **not** an experiment rerun, not a complete independent reproduction, not publication-grade causal verification.
**Source hierarchy:** original frozen source bytes > source-recorded reports > earlier chat handoffs and code recovery notes > reconstructed/estimated claims.

## Newly authenticated source material

Original ZIP filenames, complete local SHA-256, and original manifest member SHA-256 values are preserved in `historical_archive_audits` and `historical_file_index`. All original source ZIP bytes are present in the single-file portable DB.

| Original ZIP | SHA-256 | Part-index files independently checked |
|---|---|---:|
| `02_ALL_GENERATED_PATCHES.zip` | `1495e6797aec65d912ac3bc77b893cf79561f471749f78d6807fecbc619e0049` | 368 |
| `03_CODEQL_SARIF_AND_SCANS.zip` | `4896827bb45257527f7816731d2b541b9dd5c8d8d00cb8755868b6083491b2cb` | 255 |
| `04_FUNCTIONAL_TESTS_AND_TRIAGE.zip` | `7f9b56cc69b100abf31966910b8f73d178f06ae959c420efbb3dee7dfd908392` | 226 |
| `07_AGENT_PROMPTS_AND_TRACES.zip` | `d004abaafea36b9e54c8620ac456072ae74937b483608b469f9198d103c135c3` | 600 |
| `08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip` | `be86fa352995a51bd4fa560a7532f721d66e5915fb47a8445ac88984309e0064` | 11 |

**Exactly 1,460 original part-index rows all match the captured member SHA-256 and byte lengths. Five corresponding `PART_INDEX.csv` records are also preserved, giving 1,465 archive members.**

## Queryable original evidence counts

- Patch generations: **235** (65 each O1, O2, O3; 12 O, 14 W, 14 P).
- Historical complete original scan reports: **40**, with the same patch SHA-256 as their authenticated original patch.
- Original after-SARIF individual results indexed: **5998**, with original SARIF preserved.
- Source-recorded syntax/test observations (not task success): **160**.
- Older source-recorded historical workbook annotation fields: **8746**.
- Original archive text entries searchable without opening the ZIPs: **1419**.
- Distinct SHA-256 source artifacts in portable DB: **956**; deduplicated by content digest while preserving every source/path occurrence.
- The original supervisor brief PDF, dated handoff PDF, and 11 mounted research-chat notes are also stored as context sources; chat notes are **not** primary experimental results.

### Source-reported O/W/P scan observations (descriptive, not causal)

| Arm | Runs with post-SARIF | Source-reported introduced CodeQL warnings | Source-reported target-rule warning instances | Functional acceptance |
|---|---:|---:|---:|---|
| O | 12 | 21 | 7 | NOT_VALIDATED |
| W | 14 | 10 | 4 | NOT_VALIDATED |
| P | 14 | 15 | 5 | NOT_VALIDATED |

- All **40** scan reports state `functional_status=NOT_VALIDATED`. This means patch-apply or syntax success cannot be promoted to full task correctness.
- **14 unique before-SARIF SHA-256 baselines are still absent from the uploaded 5 parts**. Before counts in reports are source-reported, not independently recomputable from complete before bytes.
- **O contains only 12 cases**, whereas W and P contain 14. The absent original O cases are **08461 and 15151**; do not fill them by inference or assume arm comparability.
- The historical all-arm source summary explicitly flags issue/PR chronology, functional acceptance, and generation-cohort comparability as unverified.
- A CodeQL warning is a scanner observation, **not proof of a vulnerability, exploitability, regression or prevention**.

## Exhaustive research-stage recovery register

| Stage | Historical scientific unit / topic | Status and next recovery |
|---|---|---|
| `P00_SUPERVISOR_CONCEPT` | Original CISPA project brief and Honours proposal | Supervisor definition and 20-August handoff PDFs byte-imported; original experimental claims remain separate |
| `P01_MINER_AND_WORKFLOWS` | Initial GitHub agent workflow miner and 3,809 frozen workflows | Frozen full3809 DB missing; repo/source-code recovery is not the source dataset |
| `P02_122_FIRST_AUDIT` | Initial source-coded 122 workflows, 605 canonical findings | 122-case original master workbook already imported into v3/v4; older blind versions pending |
| `P03_FOOTPRINTS_AND_SWEXPLOIT` | F1-F5 footprint protocol and controlled attack source review | F1-F5 original audit/archive versions not yet imported |
| `P04_SCAN_COHORT` | 3,809 to 192 positive to 191 mappable workflows | Stored frozen 192/191/455/342 crosswalk exists in repository provenance notes, not complete source DB |
| `P05_PRODUCING_CHANGES` | 455 producing changes and 342 root groups | 455 producing-change raw original archive not yet imported |
| `P06_D_DOUBLE_CODING` | Independent blind A/B coding and D/D7 route adjudication | 342-root original D final, D7, independent coders, 43 disagreement records still missing |
| `P07_MATCHED_CONTROLS` | 190 matched pairs (115 same-repo) and C6/C7 results | 190 workflow control pairs and 115 same-repo history reported; raw C6/C7 evidence pending |
| `P08_NEW70` | Frozen NEW70 blind issue/PR/implementation/risk phases | Original nine-phase NEW70 frozen classifications pending |
| `P09_T1_CONTEXT` | T1 context intervention and follow-up controls | Original T1 generations/blind assessments and unresolved outcomes pending |
| `P10_T2_TRANSFER` | T2 retrieval, run comparison, semantic assessment | Original T2 transfer generations/blind assessments pending |
| `P11_S5PAIR` | S5PAIR-001 12 blinded generation runs and pilot review | Six original blinded metadata files imported, but not 12 patch/SARIF payloads |
| `P12_PREVENTION_65` | 65-case prevention-screen O1/O2/O3 generated patches | Complete 65x3 original patch bytes, three generation manifests and original statuses imported |
| `P13_COUNTERFACTUAL_14` | 14-case O/W/P historical prevention pilot | 40 original O/W/P patches + after-SARIF + tests/logs indexed; 14 original baselines missing |
| `P14_PAPER_CLAIMS` | Publication claims, primary/secondary results and versioned manuscript | No complete paper claim-to-evidence audit and no independent replication |
| `P15_RELEASE_REPRODUCIBILITY` | Private review release and Hugging Face archival copy | Correct private GitHub repo; complete HF provenance dataset not yet uploaded or hash-audited |

## Key scientific version/reconciliation rules

- The canonical study lineage reported in private GitHub `docs/RESEARCH_MAP.md` is **3,809 workflows → 192 scanner-positive → 191 mapped workflows → 455 producing changes → 342 roots**. Local archive accounting for 455-to-342 is previously reported, not re-established from frozen DB in this v4 delivery.
- D-original route totals are reported as **H=5, T=103, M=234**, while D7 is **H=6, T=103, M=233**, with **43 disputed roots**. Retain both historical source labels without overwriting or voting.
- **190 matched workflow pairs (115 same-repo)** must not be conflated with **51 decision-level pairs (31 primary)**.
- Separate scanner warning counts from confirmed security violations and whole-task functional outcomes.
- T1/T2 intervention conditions must preserve blinding and the retrospective-oracle role of a historical warning. Never pretend the agent could prospectively know its introduced warning.
- Keep all failures, partial outputs, null scanner results, source-status revisions, and changed experimental configurations as separate first-class records.
- The 20-August handoff was historically useful but can be superseded by October frozen source evidence. Do not back-project older labels into later studies.

## Highest priority original archives still to upload

1. **Canonical frozen 3,809-case SQLite:** `full3809-scanner-complete-20260829.db` with original frozen hash manifest. Before importing, independently verify the source-reported SHA-256 `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`.
2. **Original D/D7 root coder evidence:** `D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz`, `D_FINAL_COMPLETE_ROOT_PROVENANCE_v1.0.tar.gz`, `D4_ADJUDICATION_198.jsonl`, `D5_FINAL_ROOT_CENSUS_342.jsonl`, `D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv` and the frozen A/B coder output packets.
3. **Matched raw decisions:** `C6_MATCHED_POSITIVE_VS_CONTROL_v1.0.tar.gz`, `C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz`, `C6_MATCHED_PAIR_MASTER_190.csv`, original same-repo sensitivity/coding.
4. **Original provenance and NEW70:** `PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv`, `PROVENANCE_SCALEOUT_Phase6_FINAL_v1.0.zip`, `NEW70_90_LOCKED_FOR_LATER.zip`, Phase1–9 original annotations and source mappings.
5. **Real T1/T2 generations:** `T1_PRIMARY_PILOT_RUN_BUNDLES_v1.tar.gz`, `T1_V9_FULL_BLIND_REVIEW.tar.gz`, `T1_V9_BLIND_ADJUDICATION_FROZEN_v1.tar.gz`, `T2_FINAL4_RUNS_v1.zip` and T2 frozen reviews.
6. **S5PAIR original output bytes:** `S5PAIR001_12_CHAT_INPUTS.zip`, `G001_OUTPUT.zip`–`G012_OUTPUT.zip`, and original 12 SARIF/run reports; preserve blinded keys separated from results.
7. **October CodeQL original before-SARIF baselines:** all 14 distinct SHA-pinned files matching `historical_scans.source_baseline_sha256` and CodeQL version/toolchain.
8. **F1–F5 and paper audit:** `F1-F5_Blind_Real122_Audit_v1.0.xlsx`, final F1–F5 method bundles, frozen statistical test scripts/results, `ARNO_PAPER_CLAIMS_VERIFIED_v2.csv`, manuscript versions.

The **470-entry ChatGPT Library inventory** exists in the private reproducibility GitHub work branch at `docs/recovery/chatgpt_library_security_artifacts_20261025.csv` and is a locator only; individual Library archives were not imported unless their bytes are present here.

## Reviewer CLI (full commands)

After extracting the release ZIP in a new directory:

```bash
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite status
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite case 668
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite run 668 O --study OWP14
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite search "file-system-race" --limit 10
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite studies
python3 -m src.repro_store.historical_cli --vault arno_research_v4_PORTABLE_PRIVATE.sqlite verify
```

An exact original archive member can be extracted by passing its complete `member_path` to `extract --output <NEW_PATH>`. That command verifies SHA-256 and refuses to overwrite.

## Privacy/release controls

**Do not commit or publish this private .sqlite to GitHub, and do not upload it publicly to Hugging Face.** It contains original third-party source patches, logs, prompts and sensitive context. Release only after privacy, repository content license, blinding and integrity review. The source tool code and synthetic tests are suitable for the private GitHub reproducibility PR; raw evidence is not.

**No experiments, scanners, Slurm jobs, agent calls, or historical coder passes were rerun or rewritten.**