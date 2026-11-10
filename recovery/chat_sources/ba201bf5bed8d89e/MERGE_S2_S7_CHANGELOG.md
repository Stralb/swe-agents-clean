# Supplement consolidation: Table S2 and former Section S7

Date: 9 November 2026
Source: Arno_A24_FINAL_ARGUMENT_SOURCE_2026-11-09.zip

## What changed

- Combined former Table S2's scanner evidence / PR-attribution rules with former Section S7's recovered scanner version and configuration observations into a *single Table S2* in Section S1. Each scanner now appears only once in the supplement's scanner description.
- Kept the six scanner/check categories: CodeQL, Semgrep, OSV-Scanner, Trivy, internal dependency downgrade comparison and Gitleaks.
- Moved the exact archived Stage 4B blind patch-summary prompt and stage-specific evidence boundaries from former Section S7 into Section S2 beside the original annotation and validation protocols. Preserved the distinction between one verbatim prompt and other protocol descriptions.
- Removed the redundant Section S7 heading and separate scanner-configuration table; renumbered the described supplementary section span to S1--S6 in the main-paper availability statement.
- Preserved source evidence scope: CodeQL 2.25.6 observed in a V6 replay, JavaScript query pack 2.3.11 in historical logs, Trivy 0.72.0 observed in historical metadata, Trivy database update on 22 July 2026, Semgrep p/security-audit configuration, unknown executable versions for OSV-Scanner / Gitleaks / Semgrep.
- Retained the applicability warning and original-cohort 142 dependency-link evidence count.

## Verification

- LaTeX builds to a 33-page ACM Small PDF.
- All cross-references resolve; no overfull text boxes.
- Table S2 appears on p. 22; evaluation protocols on p. 23. The former Section S7 is absent. Table S7 (RQ2 matching diagnostics) remains, since table and section numbering are independent.
- No empirical counts, experimental outcomes or substantive interpretations were changed.
