# Annotation prompts and protocols

The language-model prompt and coding protocols behind the annotation stages. Each section is marked as an exact prompt, a documented protocol, or a frozen codebook; protocols are the instructions the coders followed, not literal model requests.

## A. Verbatim model prompt: blind implementation description (Stage 4B)

**Status: exact frozen prompt.**

> Describe the substantive implementation changes made by this patch. Be factual, do not infer motivation, security impact, or correctness. Summarize the main changes in one sentence.

**Inputs visible:** case ID, PR ID, changed files and metadata, actual patch/diff, evidence completeness.
**Inputs withheld:** issue text and coding, PR description/stated goal, scanner results, CVEs, severity, and merge outcome.

## B. Frozen issue Pass-1 evaluation instructions

**Status: documented protocol.**


- Visible: case ID, issue title and full issue body.
- Hidden: PR text/summaries, changed files/diffs, scanner results, CVEs/rules/severity, merge outcome, actor context and risk judgements.
- Output: one factual sentence stating the issue author's request; preserve ambiguity and only include a proposed solution if the issue explicitly includes it.
- Record a short verbatim supporting excerpt.
- No inference about maliciousness, risk, intent, security consequences or causal effect.
- Freeze the summary before purpose/specificity/scope coding.

## C. Frozen PR Pass-1 evaluation instructions

**Status: documented protocol.**


- Visible: case ID, PR title and full PR body.
- Hidden: linked issue, code diff, scanner findings, merge outcome, author history, later labels.
- Output: one neutral factual sentence about the PR's stated goal and short exact supporting excerpt.
- Preserve multiple substantive goals; when the body is sparse use the title as fallback.
- No inference about intent, vulnerability, causation or hidden instructions.
- Freeze before comparison with issue summary.

## D. Finding-to-producing-change mapping (Step 2)

**Status: frozen evidence requirements.**


For each retained canonical finding, record the exact producing change and a defensible basis: changed location, diff evidence, producing-change ID, mapping status and note. Findings may share a producing-change ID. Recorded mapping-basis vocabulary:

- `scanner_flow_added_line`
- `targeted_dependency_package_version_introduction`
- `scanner_primary_added_line`
- `dependency_package_version_hunk`
- `dependency_diff_same_hunk`
- `gitleaks_content_anchor`

The final retained link's evidence basis is not equivalent to independent manual validation.

## E. Step 3: issue request to mapped change

**Status: frozen coding rules.**

- Unit: distinct producing-change ID.
- Allowed evidence: frozen issue request summary and exact supporting excerpt; finding-producing change; changed file/line/hunk only as necessary to understand it. Issue title only as fallback.
- Exclude: PR description/goal, Stage4B/4C summaries, finding/CVE/scanner/severity/count, actor/timing/review and risk labels.
- `Direct`: operation explicitly requested or directly implements requested behaviour.
- `Side-effect` (later main-paper terminology often `Supporting`): ancillary/collateral operation, generated dependency consequence, incidental technique not itself the request.
- `Unclear`: evidence does not support confident direct/supporting distinction.
- Transitive dependencies, tests/fixtures and documentation are not direct unless actually requested.

The labels in this historical protocol are not the same as independently observing who chose an implementation mechanism.

## F. Root implementation-route evaluation codebook

**Status: frozen codebook.**


Decision order: H, then T, then M, otherwise U.

- H: pre-introduction public evidence fixes the exact mechanism.
- T: mechanical generation, dependency resolution or toolchain consequence.
- M: a concrete mechanism selected among plausible alternatives, not publicly predetermined.
- U: evidence cannot reliably distinguish H/T/M.

For M, explanation tier: T1 direct reuse, T2 strong repository precedent, T3 explicit chronology-safe guidance, T4 contextually plausible, T5 no independent public explanation after a complete bounded check. Missing material evidence requires `Incomplete`, not T5. Avoid claims about hidden prompts, private reasoning, maliciousness, agent awareness or invention.

## G. Replay evaluation inputs

**Status: arm definitions.**

The manuscript documents O (original issue), W (issue plus historical warning), P (issue plus warning-derived safety property), and separate P1-P5 guidance conditions. These define the evaluation design; the per-case messages are not reproduced here.

## Scope

Sections B to G give the protocols and codebooks. Exact model request strings are given only where marked as exact prompts: section A and the root-grouping prompt.
