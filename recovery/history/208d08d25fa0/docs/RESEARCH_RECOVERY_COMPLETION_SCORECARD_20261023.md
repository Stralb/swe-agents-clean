# Reproducibility completion and release-gate scorecard

**Checkpoint:** 23 October 2026  
**Project:** Issue→agent-associated PR scanner/security study; private recovery draft PR `Stralb/arno-research-reproducibility#1`.  
**Status:** continued evidence recovery, **NOT publication-ready** and **NOT a completely independently reproduced data pipeline**.

## Planning completion estimate (explicitly subjective)

| Workstream | Estimated completion | How to interpret |
| --- | ---: | --- |
| **Engineering and recovery infrastructure** | **~90%** | Versioned private Git evidence ledger, fail-closed consistency checks, synthetic tests, automated PR CI, no original source mutation. Still requires a complete offline real-source replay, release packaging and missing frozen inputs |
| **Scientific verification / release readiness** | **~65%** | Strong denominator/source provenance, several independent indexed C6 reconstructions, but original full D-final/D7 coding, CodeQL bases, full DB, root-level time and intervention validity remain unresolved |
| **Illustrative combined progress** | **~75%** | Judgment-weighted: `0.40 × 90% + 0.60 × 65% = 75%`; not a measured fraction of tasks, validation probability, completion date or grade prediction |

These percentages are **managerial planning estimates only**, not computed from the number of commits, tests, audited source bytes, model predictions or open checklist items. A single essential release gate can prevent valid publication even at high engineering completion. A passed CI suite attests implemented tests, **not the original empirical conclusions**.

## Source-supported scientific gates

| ID | Mandatory evidence/reconstruction | Status at this checkpoint | Why |
| --- | --- | --- | --- |
| G01 | C1/C2 frozen population and matching crosswalk | **Substantially verified, scope-limited** | 190 matched workflows; original unmatched scanner-positive cases 13918/17460; C1/C2 source hashes/membership recorded; do not infer full C6 label replay |
| G02 | Nine original paired C6 omnibus comparisons | **Partial** | Five replayed from independently source-indexed aggregate paired matrices; four still require original 190-pair raw CSV |
| G03 | Original paired bootstrap and repo-cluster uncertainty | **Partial** | Finite paired-distribution calculations possible from aggregate contingency; cannot reconstruct repo-blocked bootstrap without original pair→repo membership |
| G04 | 342 root / 455 PC / 191 root-bearing workflow population | **Verified to archival D evidence-input scope** | Original D1, D2, D export indexes and blinded A/B packet archive identities crosschecked; archive digest pinned |
| G05 | 36-root lockfile outlier, scanner finding multiplicity | **Verified for case 13918 only** | Original 36 D2 packet SHA values match archived exporter manifest; 131 distinct CF source IDs are not 131 independent vulnerabilities |
| G06 | Full original D-final/D7 route and tier decisions | **BLOCKED** | Accessible Wits D-stage A/B, agreement, adjudication and final folders are empty; source-reported route totals and 43-row differences cannot replace frozen decisions |
| G07 | Canonical resolution of 43 D/D7 disagreements | **BLOCKED** | Need original coder/adjudication records, not a mechanical majority vote or preferred later version |
| G08 | Historical CodeQL O/W/P baseline SARIF and scanner provenance | **BLOCKED** | Fourteen original key SARIF baselines and exact scanner version/pack remain unrecovered |
| G09 | Final original 3,809-workflow SQLite byte authentication | **BLOCKED** | Source-reported checksum exists; exact frozen source file has not been independently full-hashed and replayed as required |
| G10 | 342-root issue-to-actual-mechanism chronology | **Partial — new evidence counterexample** | Case 154 exporter `cumulative_diff_anchor` timestamp precedes actual target-code commit by 1019 sec and incorrectly justifies a source `NO` issue eligibility; cohort-wide direct-Git validation not complete |
| G11 | Retrospective warning vs as-of-PR advisory availability | **Partial** | Seven named advisory publication dates after associated merges checked across six workflows; no cohort-wide time-consistent advisory snapshot |
| G12 | True scanner vulnerability/exploit reachability and functionality | **BLOCKED / exploratory** | Warning presence is not exploitability, functional regression or mechanism causal effect |
| G13 | Private versioned audit tooling, source-mutation safety and CI | **Working** | Recovery PR remains draft/unmerged; synthetic and indexed checks passing; no Wits source/job modification |
| G14 | Complete manuscript claim→source traceability and publication package | **Partial** | Reproducibility claim limits documented; cannot freeze definitive paper contribution estimates while essential sources missing |

**Gate counts are not converted into the ~65% planning estimate.** They differ in scope, difficulty and scientific importance and cannot legitimately be weighted equally.

## This checkpoint's incremental work

- Independently rehashed original D2 `D2_PACKET_INDEX_342.csv` and original `SHA256SUMS.txt`; 342 coder-A + 342 blinded coder-B original packet **paths** match source root/alias index; every one of the 36 case-13918 A JSON packet hashes agrees with its archived original manifest entry.
- Refuted case-154's high-confidence feature-level timestamp as the first actual `phpTagRegex` commit; corrected interpretation in a **separate** provenance ledger, leaving the source annotation untouched.
- Added [a full original Pass-A root chronology auditor](../analysis/d_pass_a_chronology_cohort_audit.py) that pins the original 25,549,416-byte Wits Pass-A source SHA-256 `4510cd4dacf218c918b82d4dfde4afefee270ba5b147a5558e7dbe87e486e8c0`, calculates issue-vs-exported-anchor classifications across 342 roots, and emits an explicit **not verified against exact Git target line** result. CI tests use synthetic cases only; **the full 25.5 MB source file has not been run through this tool**.
- Detailed execution protocol: [Pass-A 342-root root-timing audit](D_PASS_A_342_ROOT_TEMPORAL_ELIGIBILITY_AUDIT_PROTOCOL_20261023.md). User approval required before any active Wits cluster job submission; existing original source files must remain immutable.

## Scientific next actions in order

1. Execute a **read-only** 342-root original Pass-A SHA-verified cohort triage against a permitted staged copy of the 25.5 MB source file; report resolved/unresolved introduction method and issue eligibility counts without declaring causal errors.
2. Audit first **scanner-targeted mechanism or line** introduction commits for flagged roots. Preserve original method/time values; create separate correction identities and version the eligibility question.
3. Recover the original frozen C6 pair master and replay the remaining four omnibus comparisons with correct complete-case denominators and repository clustering.
4. Recover original D-final/D7 342 classifications and associated adjudication provenance, resolve 43 conflicts; do not turn archived coder *input packets* into claimed completed coder *labels*.
5. Authenticate final SQLite plus historical scanner/CodeQL SARIF baselines, warning catalog dates, prospective functionality, and actual intervention outcomes.
6. Freeze a final scientifically defensible report only after these gates or explicitly **scope down** conclusions to what is supported for a supervisor-first draft.

**No frozen Wits data, Slurm jobs, original scanner runs, C1/C2/C6 raw observations or H/T/M labels were changed.**
