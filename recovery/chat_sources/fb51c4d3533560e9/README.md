# Arno A24 manuscript — clean supplementary exhibits

This is the 2026-11-09 supplement-layout revision of the A24 copyedited ACM Small manuscript.

## Build

Run `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` in this directory.

The supplied source consists of `main.tex`, `supplement.tex`, `figures/`, and `tables/`.
The main manuscript text was not changed in this pass; only the supplementary source has been reformatted.

## Changes

- No introductory prose under "Supplementary Material". It now leads directly into S1.
- Table S1 separated into categorical counts and continuous measurement distributions.
- GitHub corpus selection criteria moved to a clearly labelled non-floating protocol block.
- Supplementary methodology prose rewritten as structured, numbered protocols and evidence-status/case-card keys.
- Table S2 simplified to three columns while preserving the original evidence boundaries.
- All supplementary figures and tables stay below their section titles instead of floating above them.
- Original cohorts, counts, matched comparisons, replay data, and limitations retained.

## Limits

This is a presentation/layout revision, not a new verification or human re-annotation of the empirical dataset. The paper's methodological limitations still apply. The case-study-first structural reorganisation requested separately has not been performed in this pass.


Final flow pass: only three prose passages in main.tex were changed. Compile using latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex.

## Table S9 rendering clarification (2026-11-09)
The source-reported count of 2 in Neo.mjs #16735/P4 is now displayed as
2 with the raised marker (p); the count of 2 in Delegate Skills #3/P5 is
shown with the raised marker (i). Parenthesized superscript markers improve
legibility and PDF text-extraction clarity. The marker definitions are
unchanged: (p) = partial implementation, (i) = missing Stage-2 record.
No data values, research claims, or other manuscript sections were changed.
