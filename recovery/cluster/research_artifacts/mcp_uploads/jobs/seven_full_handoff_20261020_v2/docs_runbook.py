#!/usr/bin/env python3
from pathlib import Path
o=Path.home()/"research_artifacts/prevention_pilot_phase2/seven_case_complete_handoff_20261020/WORKING"
doc=r"""
# NEXT AGENT RUNBOOK — START HERE AFTER READING 00-04

This handoff is designed to be read in a new chat without another history recap or missing repository downloads FOR THE SEVEN CASES. The seven O snapshots, all seven selected final patches, intermediate repair patches, original/W/P issues, historical comparisons and SARIF are included.

## No-compute first checks

1. Read 00_START_HERE and 01_SCREENING_AND_LINEAGE. Do not confuse 65-case screen with 233 metadata roots. Record 12 intermittent positive cases and 2 incomplete second-round scans.
2. Read 02A/02B casebooks and 04 results; do NOT present '7/7 prevented vulnerabilities.' The proper preliminary statement is seven distinct scanner-negative implementations over different exploratory stages, with inadequate functional acceptance and no proven minimum issue addition.
3. Read all seven ISSUE_TREATMENTS/CASE_ID/original.md and warning oracle vs property variants. Validate source SHA and exact historical issue provenance before using as causal inputs.
4. Read PATCHES/FINAL_SELECTED for seven implementation mechanisms; compare with the original code to flag pre-existing behavior changes, including 03429 test fixture.
5. Read RESULT.json and SARIF for original and final scans; scanner finding counts alone are not proof of vulnerability. Classify previously existing alerts, newly reachable old sinks and newly added-line issues separately.

## Bundle layout and what is offline-complete

- FROZEN_REPOSITORIES/CASE_XXXXX_O.zip: the seven complete original frozen repo trees in REPO/, original issue in ISSUE.md, run instructions.
- ISSUE_TREATMENTS/CASE_XXXXX/: O/W/P actual issue texts (W oracle, P property), plus P1/P2/P3 proposals if present.
- PATCHES/FIRST_AGENT/: the seven distinct agent patch implementations; all three nominal P1/P2/P3 were exact copies so only P1 is represented as one unique patch.
- PATCHES/FINAL_SELECTED/CASE_XXXXX_FINAL_PROTOTYPE.patch: the currently scanner-negative implementation for every case, always diffed against the original O repository.
- PATCHES/INTERMEDIATE/: earlier targeted stage patches.
- CODEQL_FIRST_SEVEN/: raw 7-case first pass all before/after SARIF/logs.
- CODEQL_FINAL/: raw per-case final comparison SARIF/result/logs.
- EVIDENCE_65/: raw three-round matrix, 65x3 CASE RESULT.json, 14 O/W/P warnings and comparisons.
- EARLIER_EXPERIMENTS/: compact older patch, scanner, functional, prompts and causal archives; Wits 1.7GB exhaustive export is NOT nested.
- ANALYSIS_SCRIPTS/: CodeQL runner and generation/packaging code (Wits-specific paths may need updating).
- MANIFEST/CHECKSUM_MANIFEST.json: root SHA-256 of all copied files and missing file notes.

No new LLM generation or scanner run is required to understand these results. Executing new scans requires a CodeQL 2.25.6 installation and sufficient compute; using third-party integrations requires normal dependencies and appropriate account credentials. The complete software execution environment is NOT embedded.

## Patch application example

Unzip the handoff. For one case use the ORIGINAL O repository snapshot, NOT the previously modified O/W/P source:

    mkdir -p case_work
    unzip FROZEN_REPOSITORIES/CASE_08152_O.zip -d case_work
    cd case_work/REPO
    git apply --check ../../PATCHES/FINAL_SELECTED/CASE_08152_FINAL_PROTOTYPE.patch
    git apply ../../PATCHES/FINAL_SELECTED/CASE_08152_FINAL_PROTOTYPE.patch

If paths differ because working directory or extraction layout differs, inspect the source ZIP and patch headers; never apply to another arm's already modified REPO.

For patch integrity use CHECKSUM_MANIFEST.json and sha256sum. The final patches are full diffs relative to original R0; DO NOT apply first agent P1 and then the final full patch.

## Standard differential CodeQL protocol

Freeze pre-PR source O. Build TWO independent CodeQL DBs on same source: baseline repo and baseline+one implementation patch. Use EXACT pinned suite:

    codeql version
    codeql database create db_before --language=javascript-typescript --source-root=/absolute/path/clean/REPO --build-mode=none --threads=4 --ram=18000
    codeql database analyze db_before codeql/javascript-queries:codeql-suites/javascript-security-extended.qls --format=sarif-latest --output=before.sarif --threads=4 --ram=18000
    codeql database create db_after --language=javascript-typescript --source-root=/absolute/path/patched/REPO --build-mode=none --threads=4 --ram=18000
    codeql database analyze db_after codeql/javascript-queries:codeql-suites/javascript-security-extended.qls --format=sarif-latest --output=after.sarif --threads=4 --ram=18000

Version must be 2.25.6 or record the version deviation. Compare SARIF using fingerprint and conservative rule+file+message equivalence; don't subtract simple total counts. Example: 12344 initial first agent has 6 conservative new and 7 fingerprint new; report both, do not hide disagreement.

Original issue + addendum instructions affect ONLY independent agent generation, not CodeQL scanner itself. Never feed future/historical patch or SARIF to a prospective-agent run except a defined W oracle arm.

## What is STILL not demonstrated

- Functional/native acceptance on all seven, especially Windows BYOK and Codex; no end-to-end real-world reproducibility.
- Strict additive-only PR compliance for all final patches. 03429 changed original test fixture; 31207 shifts a secret-read across a shell process boundary.
- Minimum issue text or necessity/sufficiency. No causal P1/P2/P3 comparison because the produced 21 patches were duplicate.
- Generalization to new repos or unobserved warnings.
- True security improvement from fewer static alerts in 08152 and 31207.
- Source provenance: 03429,12344,31207 filtered/provisional; historical original issue-as-of-PR not verified.

## Recommended fastest reliable next steps

### Priority A — finish engineering adjudication without more giant sweeps
1. Native Windows DPAPI and Codex argument/shim tests on 12344 and 32759.
2. Install @grammyjs/files in an isolated 08152 checkout, update lockfile, run tsc/build/voice+bridge suite, then controlled live Telegram file API tests with safe dummy credentials; no real token in archived results.
3. Render 31207 Compose overlays, test Docker secret mount/CMD-SHELL and authenticated probe, reject env leakage on a shared multi-user threat model; do not call mere scanner evasion secure.
4. Confirm 03429 V3 touched old test fixture and assess whether historical P original is scanner-negative AND functional WITHOUT modifying pre-existing fixture. If not, strict success unavailable.
5. Test 03581 webview sender and transcript rotate; 22223 authenticated artifact download constraints.

### Priority B — the supervisor's real research
6. Freeze exact original issue text and PR-linked SHA. Pre-register acceptance checklists and exact target W vs all-new-CodeQL outcomes.
7. Rebuild a new prospective-like original O control, a hindsight full warning W arm, generic G, mechanism P and property P variants in distinct clean fresh coding-agent sessions. Do NOT reuse identical patches. Screen one generation per arm before repetitions.
8. For a functionally valid scanner-negative W/P sample, recursively remove least relevant clauses, then confirm minimal tested wordings with independent repeats.
9. Transfer frozen mechanism-property text to at least one of the 12 intermittent positives (e.g. 00668 or 04134 for race, 04379 for path) WITHOUT warning hindsight. Need source archive and cross-case prerequisites if outside these seven.
10. Report conditional rates, error bars, functional failure count and scanner model limitations. Never claim a deployable clairvoyant workflow.

## Presentation-safe 60-second findings

From a 65-case repeated original-task screen, seven produced a new CodeQL warning in ALL three generations; another 12 produced warnings only intermittently. We used retrospective warning-informed interventions and targeted engineering experiments to study how a task can be implemented without triggering the scanner. In the latest scanner comparisons, seven selected implementations have zero new CodeQL findings. However, that is NOT seven proved secure fixes: code revisions sometimes used full warning hindsight, functionality is not fully verified, a scanner warning may reflect intended authenticated dataflow, and one test-fixture repair is outside strict add-only constraints. The follow-up research question is whether the minimal warning-derived constraint, stated IN THE ORIGINAL ISSUE, causes an independent coding agent to choose the same safe mechanism WITHOUT access to the historical warning. We therefore need true separate generative arms, functional acceptance and held-out transfer.

## DO NOT

Do not run all seven baselines, 21 duplicate patches or 65 screen sources again automatically. The archives contain the results. Do not omit requested features just to achieve zero warnings. Do not create pre-PR/source evidence that was never verified. Do not confuse tests with production security or path-based taint detection with exploitability. Do not invent minimality, causal significance or holdout performance.
"""
(o/"05_NEXT_AGENT_RUNBOOK.md").write_text(doc.strip()+"\n")
(o/"PASTE_THIS_INTO_NEW_CHAT.txt").write_text("""Treat this ZIP as the ONLY required research input for the seven-case study. Read 00_START_HERE.md, 01_SCREENING_AND_LINEAGE.md, 02A/02B casebooks, 03_SUPERVISOR_CAUSAL_DESIGN.md, 04_EVALUATION_RESULTS.md and 05_NEXT_AGENT_RUNBOOK.md, then verify CHECKSUM_MANIFEST.json and raw SARIF/patched files. First answer the supervisor's questions and identify what is proven vs still hypothetical. Reuse the archived first seven and final selected patches; do not repeat scans that already exist. We have 65 screening cases (seven positive 3/3, three positive 2/3, nine positive 1 observed round, forty-five negative all three, one negative twice with missing round); 12 intermittent-positive cases are future exploration candidates. The latest seven scanner-negative implementations are feasibility results, NOT validated prevention by adding issue text. Establish functional acceptance/provenance, then plan independent minimal add-only ISSUE intervention tests. Cite exact file names and scanner evidence, and do not claim the agent can know future warnings. Everything needed to understand and reproduce the existing seven cases is in this archive; if new external cases are chosen, source files may need to be acquired.\n""")
print("WROTE",len(doc))
