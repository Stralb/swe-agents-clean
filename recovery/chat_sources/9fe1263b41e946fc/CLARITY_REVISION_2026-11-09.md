# Plain-language editorial revision — 9 November 2026

## Evidence-preserving changes

- Rewrote the abstract into shorter, distinct statements and removed the inaccurate label “finding-free”.
- Standardised three separate concepts: *finding* (one scanner report), *responsible change* (code/dependency operation linked to one or more findings), and *implementation choice* (group of related changes). Retained H/T/M/U and T1–T5 where necessary for traceability, with descriptive prose.
- Added Table 1 mapping the full corpus, finding-positive set, initial 122-instance annotation, extended 191-instance mapped set, 190 matched pairs, and 14-task replay sample (12 complete triples).
- Clarified that a control had no new findings under the checks that completed and applied; it is not “vulnerability-free”.
- Shortened and clarified the related-work comparison of Sajadi et al. (benchmark patches), Rabbi et al. (security-focused PRs) and the current study (ordinary merged issue-linked PRs).
- Simplified the description of mapping evidence, control matching, case classifications and replay interpretation without removing methodological limits.
- Replaced the unsupported Spotify repository-local precedent claim with a general standard encoding alternative and expressly noted the missing repository-specific precedent evidence.
- Removed the unsupported implication that selected PR changes were functionally correct; the conclusion now states that task correctness was not verified.
- Clarified that CodeQL identifies flagged locations while the relation to the changed PR operation and issue requires additional mapping.
- Corrected the Table S8 caption's broken reference to “item 4”; it now points to the visible replay-provenance list.
- Moved earlier classification version history to the supplement for supporting context, leaving the primary results with the primary classification only.
- Replaced remaining internal shorthand (“M roots”, “mechanism origin”, “source-reported” in reader-facing definitions, etc.) with plainer descriptions where possible.

## Unchanged research facts and constraints

- Corpus and denominator counts: 3,809 instances; 192 finding-positive; original 122 positives, 605 findings, 322 responsible changes; extended 191 mapped positive instances, 455 changes and 342 implementation choices; 190 matched pairs; 14 O/W/P tasks, 12 complete triples.
- Methodological restrictions, scan counts, categorical definitions, original/updated classification versions, statistical results, RQ3 arms and case evidence remain as originally reported.
- No new experiment, annotation reliability estimate, manual validation or scanner rerun is claimed.
- Existing DOI/citation entries, RQ3 results, figures, scanner configuration appendix and Data and Code Availability statement remain included.

## Build / QA

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` completed (33 pages).
- All cross-references resolved, no overfull-box warnings in the final build; page montages inspected.
- References remain on their own page, and supplementary material still begins on a separate page.
