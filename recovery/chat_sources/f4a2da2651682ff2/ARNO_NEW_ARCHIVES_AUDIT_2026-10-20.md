# Arno research: second source-batch verification and Windows exporter repair

Date: 2026-10-20. Scope: seven newly attached research archives and the local Windows PowerShell exporter failure. This report reads archive metadata and source text without executing experiment pipelines or modifying Wits cluster files.

## 1. Windows export failure

The original `Arno_Cluster_ReadOnly_Export_Windows.ps1` reached the SSH login and completed the directory-inventory step, then threw at the source/archive inventory command. The failing command used GNU `find` predicates with nested parentheses/backslashes and quoted `-name` wildcards. Windows OpenSSH/PowerShell argument handling may alter those quotes. Also, `find` can return status 1 when some directories are inaccessible after producing useful partial output. The original code treated *any* nonzero exit as a fatal error. The earlier `HOME=/home-mscluster/astraussn` output is an additional sign that shell quoting of `printf "HOME=%s\n"` did not survive as intended.

The replacement `Arno_Cluster_ReadOnly_Export_Windows_v2.ps1` uses a simple remote `find ... -type f -print` and filters extensions **locally**; it reports nonzero `find` exit codes as incomplete inventory rather than discarding partial results; uses simple `id -un; pwd` for identity; records the miner's available Git log; and downloads its source using a binary-safe `tar -czf -` stream into a file on the Windows PC. Archive lists and SHA-256 are generated locally. It excludes known credential/bulk-data paths and does not submit jobs or write files on Wits.

**Execution status:** Script statically reviewed but **not executed on the user's Windows computer**; success cannot be guaranteed. The source-only exclusion policy is deliberate and is **not a complete preservation of runtime data**. File name inventory reaches only maximum depth 5 and may be incomplete where permissions prevent reading. If the miner is actually located under an alternate directory, report it rather than silently changing paths.

## 2. New research archive checks

| Uploaded archive | Original members | Internal SHA-256 checks | Interpretation |
| --- | ---: | --- | --- |
| Full-corpus discovery v2.1 analysis *source* | 14 | No embedded member hash ledger | Includes 7 parseable Python files, setup/test scripts, and methodological notes; **not run here** |
| Full-corpus discovery v2.1 *results* | 62 | No embedded member hash ledger | `FINAL_STATUS_V21.json` reports PASS; complete outcome-blind results, subject to dependency/source verification |
| Decision-level controls Step 4 | 14 | 13/13 PASS | Frozen 51 decision-level pairs drawn from an earlier selected 55-root population |
| Decision-level controls Step 5 | 12 | 11/11 PASS | All 102 blinded sides coded and frozen; original key exposure prompted an explicit reblinding protocol |
| Provenance closure Step 2 | 12 | 11/11 PASS | Observable-source census for 455 mapped producing changes |
| Provenance closure Step 3 | 13 | 12/12 PASS | Deep explanatory reconstruction of **56 selected roots**, not all 342 |
| Provenance Phase 7 validation | 13 | 12/12 PASS | Correction layer for 455 producing changes with 26 changed rows; does not resolve the **later D7 root-tier conflict** |

All 140 file members across these seven archives were readable, and their byte sizes and SHA-256 digests are recorded in the accompanying `NEW_BATCH_ARCHIVE_MEMBER_SHA256.csv`. The seven Python sources in v2.1 passed Python syntax parsing. These checks validate **archive consistency**, not the semantic correctness of all statistics or scripts.

## 3. Scientifically important distinctions

### Full-corpus discovery v2.1

The results archive's `FINAL_STATUS_V21.json` states completed 2026-08-30 08:27:18 UTC, PASS, 3,485 catalogued discoveries and 1,950 internal Grade A discoveries. The report describes correction of generated-feature leakage, absence+absence patterns, mixed-type effect calculation, asymmetric add/delete baselines, and use of repository-blocked null/stability tests. It reports `security_outcomes_read=false` and `outcome_overlay_performed=false`.

This makes **v2.1 the completed corrected outcome-blind discovery implementation among the versions inspected**; it does not imply every Grade A candidate is a security finding or worth a paper claim. The implementation consumes representation artifacts from v2.0, so independent regeneration requires v2.0's exact frozen source outputs and environment. The currently inspected v2.2 cluster folder has a passing *audit checkpoint only*, not a demonstrated finished v2.2 pipeline.

### Decision-level controls Step 4 / Step 5

Step 4's QC: 55 legacy non-human-prescribed roots -> 51 matched to scanner-negative decisions, with 4 deliberately unmatched. The prespecified 31 stronger pairs form the primary analysis; 20 weaker pairs form sensitivity. The scanner-negative sides are **not human-validated secure**. The 55-root study is a selected subset and cannot be treated as the 233/234-root full population.

Step 5's QC: 102 coded blinded sides / 51 pairs, 31 primary and 20 sensitivity. It explicitly records that two rows of the original Step-4 sealed key were inadvertently exposed during artifact inspection; all pairs were re-randomized and an additional sealed reblinding key used. Repository-wide precedent and local safer alternatives were **not confirmatorily coded** for Step 5 because symmetric pre-change repository evidence was unavailable. Those variables must not be backfilled as if they were prespecified.

### Observable provenance Step 2 / Step 3

Step 2 establishes the source-of-mechanism census for **455** mapped producing changes (9 exact public human prescriptions, 63 repository precedents, 102 toolchain/generated, 139 multiple/unresolved observable sources, 142 no observable precursor found). It reports 455/455 bounded search packets and zero repository-search read failures, but only 414/455 resolved introduction commits; 41 unresolved are dependency/lockfile cases. This is an **observable public-source** study, not model-intent attribution.

Step 3 is an earlier *deep-reconstruction subset*: 56 roots representing 77 producing changes; one human-fixed root leaves 55 mechanism-choice roots. Its T1/T2/T3/T4/T5 counts for choice roots are 3/6/6/29/11. Its 10 challenged Phase-7 B3 rows were reclassified to B1 (8) and B4 (2), but that is a targeted sensitivity overlay, **not a new population-level provenance census**.

### Phase 7 provenance vs D7 root holdout

The uploaded `PROVENANCE_Phase7_Validation_FINAL_v1.0` was completed **2026-09-02** at the producing-change level. It corrected 26 rows. It is **not** the same dataset or stage as `D7_DISCOVERY_HOLDOUT_BUNDLE_GPT56SOL_v1.0`, the later 342-root holdout analysis. Therefore it does not resolve the previously identified discrepancy between `D_FINAL_COMPLETE_ROOT_PROVENANCE_v1.0` (H=5, M=234, T=103) and separate D7 (H=6, M=233, T=103; 43 tier changes). Retain both; find the D7 provenance/manifest/authoritative adjudication that justifies differences before choosing one.

## 4. Current priority next sources

1. **Live current miner source**: successful `miner_live_source_readonly.tar.gz`, `miner_git_log_last500.txt`, and `candidate_sources_archives_depth5.txt` from the new Windows exporter. Review archives for sensitive files first. The August code snapshots are insufficient to establish final executable implementation.
2. **D-stage correction/freeze lineage**: D7 final root input/coding/adjudication correction ledger, including `CROOT-00649-01`, to reconcile the one H/M change and 43 tier differences. The September 2 Phase 7 producing-change ledger is not a substitute.
3. **Full-corpus discovery v2.0 inputs**: `full_corpus_deep_discovery_v2_INTERPRETATION_20260830.tar.gz` and any exact representation artifact source/fingerprint required to execute the supplied v2.1 code.
4. **Runnable matching/annotation builders**: these Step 4/5 ZIPs contain frozen data, worksheets, and methods, but no complete standalone deterministic matching and blinded-packet generation source scripts. Search archived worktrees and cluster for their exact generators.
5. **Existing pre-change and scanner sources**: query packs, scanner versions, base/head snapshots, fingerprint attribution logic, and execution manifests before claiming scanner reproducibility.

Read-only scope on Wits must remain: do not modify remote data, cancel jobs, submit jobs, or change permissions. No source archive should include authentication tokens or unredacted credentials.
