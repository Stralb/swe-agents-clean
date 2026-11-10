# Arno Research: next-chat handoff (19 October 2026)

There are two complementary sets of artifacts: this LOCAL package contains everything provided in the conversation as local files, plus derived cross-generation case flags. The main WITS SCANNER package (filename below) contains 2,501 research entries including per-case SARIF traces and agent treatment prompts not bundled here.

## Download the scanner pack (46,782,422 bytes)

/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/owp_research_handoff_job71701/OWP_65x3_14OWP_RESEARCH_HANDOFF.zip
SHA-256: a31c58014b37112b30942acf60d53c2dfa253499f705b3707f27b130d48cd62a

Use DOWNLOAD_SCANNER_ARCHIVE_FROM_WITS.ps1. It must be run by the user on a machine authorized to SSH to Wits.

## Experiment evidence

- 65 selected tasks have 3 independent O patch generation rounds.
- O1: 9 strong CodeQL-positive tasks; O2: 12; O3: 15.
- Union across O1/O2/O3: 19 distinct positive cases (NOT 19 cases matching historical warning).
- 7 positive in all 3; 3 positive in 2; 9 positive in only 1.
- O2 CodeQL scan failed on cases 16633 and 25473; neither is a scanner-negative observation in O2.
- Cohort 14 historical-warning candidates; five new exploratory O3 positives 4134,4379,6150,16209,16213.
- No additional O3 cases meet strict criterion historical warning class + added line + full source.
- 12 O patches plus all 14 W and P patches from counterfactual O/W/P are included locally, with the source ZIPs under research_files.
- Full 14-arm scanner results and SARIF are in Wits scanner pack.

## Scientific cautions

1. Rule recurrence is not equivalent to same vulnerability mechanism; compare the source-to-sink path and context.
2. R1/R2/R3 changed models and/or generation setup; clustering across them is not a pure stochasticity estimate.
3. Presence/absence of a scanner alert is not equal to exploitability or functional completion.
4. W and P are independent counterfactual implementations, not direct modifications of O.
5. Historical warning content given to W is retrospective oracle information, not ordinarily known before initial implementation.
6. Wits scanner pack intentionally omits 107 large frozen repository ZIPs; references and hashes on Wits enable reconstruction.

## Original local attachments

`research_files/` includes the complete local patch archives, research summaries, manual evaluation sheet and source notes. `reference_pdfs/` includes available academic PDFs.

## Next chat priorities

- Read this file and CROSS_GENERATION_65_TASKS.csv.
- If investigating exact CodeQL traces, use the Wits scanner ZIP and archived per-case SARIF; do not infer from summary statistics.
- Inspect issue-vs-patch taxonomy labels (including whether changes were direct or incidental) separately from warning root cause.
- Stratify persistent same-rule findings from different-rule findings and task coverage.
- Maintain original SHA/frozen repository as experimental input provenance.
