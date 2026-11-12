# ARNO RESEARCH — NEXT CHAT HANDOFF (2026-10-19)

## Start here
This local ZIP includes code/patch archives and all reports **present in the ChatGPT mounted workspace**, plus the correspondence, methodology notes, source PDFs and aggregate CodeQL tables. It is not the Wits cluster filesystem: FULL raw per-run SARIF, all 65×3 individual `RESULT.json` files and all full frozen repository snapshots have NOT been transferred into this ZIP. Raw results are preserved on Wits; paths below.

## Three generations — verified
- 65 frozen tasks underwent 3 LLM patch generations. Source selection based on a larger historical pipeline; **do not say that all 100 were scanned three times** without verifying denominator.
- Round 1 = 9 tasks with >=1 **new strong** CodeQL finding; Round 2 = 12 with >=1 new strong finding **with 2 scan failures: 16633,25473**; Round 3 = 15 with >=1 new strong finding (65/65 scan complete).
- 19 unique scanner-positive task IDs across 3 generations: see `HANDOFF/CROSS_GENERATION_POSITIVES.csv`.
- 7 cases positive in all 3; 3 positive in 2; 9 positive in 1. This is **task-level association**, NOT proof the same source-to-sink mechanism occurred all 3 rounds.
- Recurrently same rule family in all 3 for five cases: 03429, 03581, 08152, 12344, 31207 (rule matching is a first pass, not source-to-sink adjudication). 22223 and 32759 have changing rule families despite 3/3 positivity.
- Cross-generation setup may change model/prompt => term **cross-generation variability**, not measured decoding nondeterminism.

## Archive identification (IMPORTANT)
- `research_files/SCREEN_ALL_65_PATCHES(1).zip` = 65 O2 patch set, verified `O_CASE_00668.patch` sha256 8bc85fcf... ; O2 scan folder `screen65_second_codeql_job70782`.
- `research_files/SCREEN_RESULTS_65_PATCHES_AUDITED (1).zip` = 65 O3 patch set, verified `O_CASE_00668.patch` sha256 9ba5f3b5... ; O3 scan folder `screen65_iter3_codeql_job71507`.
- `research_files/all_case_patches.zip` = 12 O patches in matched 14-case O/W/P study; O's two missing patches 08461_O,15151_O. Do not mistake this subset for 65 O1.
- `research_files/ALL_14_CASE_PATCHES.zip` = all 14 W patches.
- `research_files/ALL_CASES_PATCHES.zip` = all 14 P patches.
- `research_files/OWP14_Three_Arm_Research_Results.zip` = O/W/P scanner comparison + JSON.
- `research_files/OWP14_Validity_Triage_Results.zip` = function/syntax triage, watcher and mocked-voice tests.
- `research_files/OWP14_Target_Finding_Adjudication.md` = source-to-sink/manual review findings (read caveats).
- `research_files/dual_o_14_case_full_audit_and_owp_runbook.md` = methodological record.
- Most upstream source archives, O1 case-specific patches and first-iteration SARIF are **on Wits only**.

## Wits cluster
- SSH user: astrauss, root: `~/research_artifacts/`, or `/home-mscluster/astrauss/research_artifacts`.
- R1 scan: `prevention_pilot_phase2/screen65_codeql_job70675/` (65 cases, `RESULT.json`, SARIF); summary `screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv`.
- R2 scan: `prevention_pilot_phase2/screen65_second_codeql_job70782/` (65 case folders), patch source: `screen65_second_20261018_v1/patches/`.
- R3 scan: `prevention_pilot_phase2/screen65_iter3_codeql_job71507/` (`SCREEN65_ITER3_SUMMARY.json`, `SCREEN65_ITER3_RESULTS.csv`, per-case `RESULT.json`, after SARIF), generated patch staging `screen65_iter3_staged_20261019_v2_bigbatch/`.
- OWP frozen input packet ZIPs: `prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_NNNNN_{O,W,P}.zip` (repo + original issue + interventions; potentially GB total).
- OWP O scan `prevention_pilot_phase2/owp14_user12_o_codeql_job71159/`, W scan `owp14_user14_w_codeql_job71209/`, P scan `owp14_user14_p_codeql_job71204/`.
- OWP final comparison: `prevention_pilot_phase2/owp14_allarm_comparison_job71212/OWP14_SCANNER_COMPARISON.csv` and `.md`.
- Syntax checks: `owp14_syntax_jsx_checks_job71362/`; targeted behavior: `owp14_targeted_behavior_job71363/`; research intake prompts: `owp14_functional_intake_job71357/`.
- Some snapshot types `FILTERED_SOURCE_PROVISIONAL`; don't claim full-repo validation in those cases.

## Preventive experiments
- O original issue only, W issue + historical rule and brief diagnostic, P issue + property-level preventive instruction.
- W and P each 14 patches, 12 have contemporaneous O counterpart in matched study. Only 4 full snapshot matched cases had O's selected historical rule on changed lines (00668,03581,08152,22223).
- 03581 W/P eliminate watcher race; 00668 W/P retain file race; 08152 W still flags bot-token network flow, P flags two related flows despite defensive path checks; 22223 W/P retain required untrusted-network-to-file flow. 03429 P mitigates insecure temporary file but filtered source. 31207 W omits implicated healthcheck operation so disappearance is not safe completion.
- Finding reductions alone are not vulnerabilities prevented; scanner classification and functional completion distinct.

## Recommended next chat
1. **Retrieve all 3 rounds' raw CodeQL differential results and summarize overlaps** (see filenames above), preserve failures as NA. Do not conflate exact rule and same mechanism.
2. Map each issue task objective, stated remedy, generated patch behavior, and CodeQL source-to-sink trace into the earlier blinded taxonomy (direct/side-effect/unclear or issue mechanism-selection etc). Do not retrofit labels from outcome.
3. Focused mechanism-specific prompting experiment with held-fixed model and repo, contrasting information sufficiency, instruction steering and scanner-feedback repair.
4. Cite provenance for each claim and keep the original issues, prior PR warnings and generation-specific interventions separate.

## Integrity
Everything under `research_files` and `reference_pdfs` is copied byte-for-byte. `MANIFEST.json` inventories and SHA-256 hashes each source. `HANDOFF/` files are created as interpretive indexes, not new scanner evidence.
