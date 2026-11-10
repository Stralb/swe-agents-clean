# Extracted evaluation prompts and frozen annotation protocols

Source scope: V6 Wits research artifacts and the original 122-case workbook, checked 2026-11-09. Exact prompts are explicitly distinguished from procedural instructions; neither is reconstructed or fictionalised.

## A. Verbatim model prompt: blind implementation description (Stage 4B)

**Status: EXACT frozen prompt.** Independently attested by the 122-case workbook (`Stage4B_Protocol!B4`) and V6 `new70_frozen_methodology_LATEST/99_MANIFEST/FROZEN_ORIGINAL_122_METHOD.txt`.

> Describe the substantive implementation changes made by this patch. Be factual, do not infer motivation, security impact, or correctness. Summarize the main changes in one sentence.

**Inputs visible:** case ID, PR ID, changed files and metadata, actual patch/diff, evidence completeness.
**Inputs withheld:** issue text and coding, PR description/stated goal, scanner results, CVEs, severity, and merge outcome.

## B. Frozen issue Pass-1 evaluation instructions

**Status: DOCUMENTED PROTOCOL, not an authenticated literal LLM request.**

Source: V6 `new70_frozen_methodology_LATEST/01_ISSUE_PASS1_BLIND/PROTOCOL.txt`.

- Visible: case ID, issue title and full issue body.
- Hidden: PR text/summaries, changed files/diffs, scanner results, CVEs/rules/severity, merge outcome, actor context and risk judgements.
- Output: one factual sentence stating the issue author's request; preserve ambiguity and only include a proposed solution if the issue explicitly includes it.
- Record a short verbatim supporting excerpt.
- No inference about maliciousness, risk, intent, security consequences or causal effect.
- Freeze the summary before purpose/specificity/scope coding.

## C. Frozen PR Pass-1 evaluation instructions

**Status: DOCUMENTED PROTOCOL, not an authenticated literal LLM request.**

Source: V6 `new70_frozen_methodology_LATEST/02_PR_PASS1_BLIND/PROTOCOL.txt`.

- Visible: case ID, PR title and full PR body.
- Hidden: linked issue, code diff, scanner findings, merge outcome, author history, later labels.
- Output: one neutral factual sentence about the PR's stated goal and short exact supporting excerpt.
- Preserve multiple substantive goals; when the body is sparse use the title as fallback.
- No inference about intent, vulnerability, causation or hidden instructions.
- Freeze before comparison with issue summary.

## D. Finding-to-producing-change mapping (Step 2)

**Status: FROZEN EVIDENCE REQUIREMENTS, not recovered literal model prompt.**

Source: V6 `new70_frozen_methodology_LATEST/99_MANIFEST/FROZEN_ORIGINAL_122_METHOD.txt`, steps 11-12.

For each retained canonical finding, record the exact producing change and a defensible basis: changed location, diff evidence, producing-change ID, mapping status and note. Findings may share a producing-change ID. Recorded mapping-basis vocabulary:

- `scanner_flow_added_line`
- `targeted_dependency_package_version_introduction`
- `scanner_primary_added_line`
- `dependency_package_version_hunk`
- `dependency_diff_same_hunk`
- `gitleaks_content_anchor`

The final retained link's evidence basis is not equivalent to independent manual validation.

## E. Step 3: issue request to mapped change

**Status: FROZEN CODING RULES, not recovered literal model prompt.**

Source: same V6 frozen-original-122 manifest, step 13, and original handoff Appendix B.

- Unit: distinct producing-change ID.
- Allowed evidence: frozen issue request summary and exact supporting excerpt; finding-producing change; changed file/line/hunk only as necessary to understand it. Issue title only as fallback.
- Exclude: PR description/goal, Stage4B/4C summaries, finding/CVE/scanner/severity/count, actor/timing/review and risk labels.
- `Direct`: operation explicitly requested or directly implements requested behaviour.
- `Side-effect` (later main-paper terminology often `Supporting`): ancillary/collateral operation, generated dependency consequence, incidental technique not itself the request.
- `Unclear`: evidence does not support confident direct/supporting distinction.
- Transitive dependencies, tests/fixtures and documentation are not direct unless actually requested.

The labels in this historical protocol are not the same as independently observing who chose an implementation mechanism.

## F. Root implementation-route evaluation codebook

**Status: FROZEN CODEBOOK, not recovered literal per-case model prompt.**

Source: V6 `D_COMPLETE_ROOT_PROVENANCE_v1_0/00_FROZEN/D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md`.

Decision order: H, then T, then M, otherwise U.

- H: pre-introduction public evidence fixes the exact mechanism.
- T: mechanical generation, dependency resolution or toolchain consequence.
- M: a concrete mechanism selected among plausible alternatives, not publicly predetermined.
- U: evidence cannot reliably distinguish H/T/M.

For M, explanation tier: T1 direct reuse, T2 strong repository precedent, T3 explicit chronology-safe guidance, T4 contextually plausible, T5 no independent public explanation after a complete bounded check. Missing material evidence requires `Incomplete`, not T5. Avoid claims about hidden prompts, private reasoning, maliciousness, agent awareness or invention.

## G. Replay evaluation inputs

**Status: STUDY ARM DEFINITIONS ONLY; exact per-case messages not recovered.**

The manuscript documents O (original issue), W (issue plus historical warning), P (issue plus warning-derived safety property), and separate P1-P5 guidance conditions. These descriptions explain evaluation design, but are NOT exported as verbatim model prompts. Do not claim to have recovered exact warning text, property wording or complete invocation metadata for every run.

## Not recovered / not substituted

- Exact model API invocation strings, full system messages and per-case prompt packets for all 122+70 annotation stages.
- Exact original Step-2 mapping requests for all producing changes.
- Complete original O/W/P and P1-P5 per-case generation prompts and settings.

These are not manufactured from high-level protocols.
