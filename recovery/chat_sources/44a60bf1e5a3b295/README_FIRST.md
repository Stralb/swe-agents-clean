# Verified research handoff — two principal CSVs

1. `ARNO_PAPER_CLAIMS_VERIFIED_v2.csv`: **70** distinct research claims, results, qualifications, alternatives and rejected overstatements, normalized from the prior 50-row decision register and fully accounted 47-row historic claim ledger (47 IDs mapped, not redundantly counted as 47 independent results).
2. `ARNO_RESEARCH_PROGRESSION_VERIFIED_v2.csv`: **275** original curated research-history records with their 29 source fields preserved, plus verified source SHA-256/line-span integrity, evolution-link counts, chronological uncertainty, and paper-use warnings.

**Important:** the word VERIFIED has a *bounded scope* here. Source-row recounts and archival provenance checks verify what the sources actually record, not whether scanners, mechanism attribution, the original case timelines, or human/causal claims are scientifically established.

## Categories
- `DIRECT_CLUSTER_SOURCE_RECOUNT`: 3,809/192/3,617 counted from the actual Wits C1 CSV in chunked read-only remote access; no scanner rerun.
- `INDEPENDENT_LOCAL_SOURCE_RECOUNT`: direct row/ID/crosswalk recount from Wits export or historical workbook.
- `INDEPENDENT_REPO_CSV_RECOUNT`: direct recount from private-repo CSV (case-arm source and patch-scope source); no before/after CodeQL rerun.
- `HISTORICAL_CODING_LABELS_RECOUNTED`: numbers are real archived *labels*, not externally adjudicated truth.
- `HISTORICAL_RESULT_NOT_ROW_REPRODUCED`: previous result exists, but primary semantic label rows / tests were not in provided evidence.
- `SUPERSEDED_HISTORICAL_INTERPRETATION`: do not use legacy inference as final result.
- `NO_SUPPORT_FOR_PROPOSED_INFERENCE`: do not state it as a finding.
- `HISTORICAL_PRESENTATION_ONLY`: earlier research notes, not current sample estimate.

## Practical manuscript use
Read the paper claims CSV first, filter on `manuscript_decision`, read `verification_status` and `critical_caveat_or_missing_proof`, then use approved *scoped* wording. In the manuscript, describe the research as empirical observation of scanner-associated changes, not confirmed agent-created exploitable vulnerabilities. Avoid blanket verification-progress sections, but do not claim tests, independent human consensus, source-authorship proof, or prevention results that never occurred.

Progression archive is an editorial historiography: the 17 stages are *logical* not verified dated chat chronology. An exact duplicate saved exchange exists (C077 duplicates C076). Original historical sources are available in the separate `ARNO_RESEARCH_INTELLECTUAL_HISTORY_v1_0.zip`, which is not bundled here. None of the original sources or user review files were modified.

## Critical results
- 3,809 selected workflows, 192 scanner-positive and 3,617 comparator pool (direct cluster row recount).
- 455 PC records, 191 workflow IDs, 342 roots and exact one-to-one PC-to-root assignment (direct local recount).
- 190 unique matches, 115 same repository, 75 cross repository (direct local recount).
- 122 older cases, 605 canonical findings, 322 producing changes (direct workbook recount).
- O/W/P: 14 cases, 12 complete triples; 12/14/14 scans; O=21, W=10, P=15 *claimed* new alerts (source-row recount, not independent baseline differential).
- 41/455 introduction records unresolved, and 12/342 root boundary uncertainty flags.

If new user sources supply paired category rows, baseline SARIF, or final D7 adjudications, those can be inspected in the new session. A missing proof stays missing; prior summary repetition is not independent confirmation.

## Contents added for standalone use
Original exported Wits 89-case ZIP, original full intellectual-history ZIP, historic 122 workbook, O/W/P original repository CSV, and the user's original master directive are included. In a new chat, attach the whole bundle (or extract and attach the two CSVs + evidence ZIP + source archive) to retain primary evidence. The private GitHub source is connector-accessed, not copied wholesale.

Use `NEW_CHAT_PROMPT_VERIFIED_v2.md` only after reading the verified claims CSV.
