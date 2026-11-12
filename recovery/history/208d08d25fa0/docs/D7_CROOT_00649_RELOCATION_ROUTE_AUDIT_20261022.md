# D/D7 conflict and inherited-code scanner attribution: CROOT-00649-01

**Audit date:** 22 October 2026  
**Status:** `SOURCE_RELOCATION_EVIDENCE_CONFIRMED__D_ROUTE_UNRESOLVED__SCANNER_BASELINE_NOT_ATTESTED`

## Why this root merits priority

The frozen [D/D7 differences ledger](../provenance/d_vs_d7_label_differences.csv) records **CROOT-00649-01** as the sole route-level conflict: D-final **M/T1** versus D7 **H/NA**. The other 42 differences change only an M-root explanation tier. Of the 43 disputes, **17 involve an INCOMPLETE tier** in one version; 25 are complete-tier-only changes. This is not 43 independently proven annotation errors; it is a targeted adjudication backlog.

The original Wits D2 blind-A evidence packet is at:
`D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/by_root_A/CROOT-00649-01.json`.
It maps the root to one producing change and a CodeQL `js/incomplete-sanitization` finding in `src/shared/format-terminal-path.ts` at line 74, reporting unescaped backslash characters. Its `chronology` object is empty and its `explicit_chronology_fields_available` flag is false. Its available Phase4 precursor evidence cites pre-existing escaping operations in `src/main/file-dragdrop-handler.ts`.

The authoritative frozen Wits D0 route codebook is preserved at `D_COMPLETE_ROOT_PROVENANCE_v1_0/00_FROZEN/D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md`. It requires an H mechanism to have been fixed by chronology-safe *public pre-introduction* evidence; merely observing an exact prior example is insufficient to infer that the issue mandated the implementation. T1 is instead a reuse/near-copy explanation **for an M route**. The recorded summary-level comparison is separately audited in [the D-versus-D7 evidence gate](FROZEN_EVIDENCE_REPLAY_GATES.md).

## Independently inspected public source and time ordering

- [Issue #84](https://github.com/carloluisito/omnidesk/issues/84) was created **20 July 2026 08:38:00 UTC**.
- [PR #87](https://github.com/carloluisito/omnidesk/pull/87) was created **20 July 2026 08:52:56 UTC** and merged at **10:35:48 UTC**.
- The issue currently specifies fixing POSIX quoting/escaping, moving duplicate functions to shared code, and preserving or deferring Windows behavior; it was last updated **10:35:49 UTC**, essentially at PR merge time. Its **body as of 08:52:56 UTC has not been independently pinned**. A currently visible body cannot be assumed to be the unchanged original.
- The actual base commit matches the preserved case's database metadata: `2590e0b27883478ff8b94106614057b7bc99a980`; the actual head commit is `a71cfaf0dadca4213a9f00838c1cb28b4b894367`.

The original base renderer function [`src/renderer/components/Terminal.tsx` at base](https://github.com/carloluisito/omnidesk/blob/2590e0b27883478ff8b94106614057b7bc99a980/src/renderer/components/Terminal.tsx#L19-L52) has the *same five successive escaping replacements*, in the same order, as the Windows escaped-mode branch of the [new shared function at head](https://github.com/carloluisito/omnidesk/blob/a71cfaf0dadca4213a9f00838c1cb28b4b894367/src/shared/format-terminal-path.ts#L70-L80). A direct line-normalized five-line comparison returned **exact textual equality**. The base `src/main/file-dragdrop-handler.ts` also contains the same chain. That establishes pre-existence of the textual mechanism before this PR.

## Read-only CodeQL provenance inspection

Read-only queries against `miner.agentic-js.eval.20260720_224159.full3809-continuation.db` (a **later continuation candidate**, not SHA-authenticated final August 29 SQLite) returned:

- Five stored `scanner_findings` rows for the affected case, all `codeql / js/incomplete-sanitization`, all pointing at the new shared file and line 74, each with `introduced=1`.
- Both `codeql-javascript-typescript-base` and `...-head` scanner runs were `ok`; the archived `codeql` summary reports `introduced_total=5`, `diff_linked=5`, `security_diff_linked=5`. These are **archived scanner claims**, not independent baseline recomputation.
- The stored raw head finding contains a CodeQL fingerprint at the new path and a warning about unescaped backslashes. It does not itself enumerate matching base-file warnings.
- A direct JSON-field query of **all five** stored head findings found **the same rule, same path, start line 74, primary location-line hash `d9ac97afaab7de15:1`, and start-column fingerprint `12`**. Their reported end lines differ **79, 78, 77, 76, 75**. Five scanner rows are therefore **not five distinct root mechanisms** and may represent overlapping CodeQL sanitization stages or one repeated source-locator fingerprint; whether they are logically duplicate warnings requires original SARIF/code-flow analysis. Do not collapse them merely by identical primary hash or treat them as five independent regressions.
- The source file has one root decision / producing-change mapping. **Five stored scanner findings must not be conflated with five independently chosen mechanisms.**

The literal old/new sanitizer chain equality supports a **relocation/inherited-code explanation worth testing**. It is **not** a proof that the full functions, call-path reachability, dataflow, parser assumptions, or observed behavior are unchanged. In particular, a warning can be new relative to the scanner's path/fingerprint matching even when relevant code lines were copied unchanged. Equally, a newly reachable vulnerable use could create real risk despite a copied helper.

## Classification and threat-to-validity verdict

**Current decision: retain UNRESOLVED route conflict. Do not overwrite either D-final M/T1 or D7 H/NA.**

- **H is plausible** if a verified issue snapshot before PR creation specifically required preserving the exact Windows sanitizer behavior, thereby fixing this root's mechanism.
- **M/T1 is plausible** if the issue only constrained the broader POSIX repair and preserved Windows functionality without prescribing these exact operations; the implementer then chose to reuse the existing chain from plausible alternatives.
- Neither label can be decided merely because the new text matches preexisting code. H applies to *pre-change prescription*, whereas T1 applies to an *M root's explanation by reuse*.

A separate **introduced-warning vs introduced-vulnerability** concern remains: a preexisting, potentially insecure Windows sanitization chain was moved to a new path and reported as a new CodeQL alert. The study must verify base/head rule-level SARIF and compare semantic path reachability before calling this a newly introduced defect or claiming it was prospectively avoidable.

## Evidence required to close this specific dispute

1. Independently preserve the issue's *content at or before 08:52:56 UTC*, including edits and relevant pre-introduction comments. GitHub's current issue body is insufficient because its last-update timestamp is after PR creation.
2. Retrieve exact original CodeQL base/head SARIF for this case, with tool/QL pack identity, and inspect base alerts at both original source locations. Hash-match against the frozen scanner export where possible.
3. Compare original and new execution paths (POSIX vs Windows, call sites and `isWindows` propagation), not just the five identical statements.
4. Obtain D-final coder/adjudication explanation and D7 independent rationale, then blind-adjudicate the specific H-versus-M question under frozen D0 definitions.
5. Keep the finding in the original study population during sensitivity analysis and report both frozen classifications until the above evidence is conclusive.

No production scan, historical annotation rewrite, Slurm job submission or Wits file modification occurred. Public repository/code metadata and aggregate read-only scanner facts only were placed in this note.
