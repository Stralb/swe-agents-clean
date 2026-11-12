# A24 plain-language manuscript revision (9 November 2026)

This is an editorial revision of the latest layout-polished A24 source, not a new empirical analysis. It preserves the main manuscript, supplement, tables, and recovered figures.

## Build

From this directory, with LaTeX and the acmart class installed:

    latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

The rendered PDF is also included as main.pdf.

## Evidence

- The linked GitHub repository is the study's existing code repository.
- Scanner versions and model/evaluation prompt evidence are under reproducibility/.
- No new scan, independent human annotation, functional test, or causal claim was added.

See CLARITY_REVISION_2026-11-09.md and PLAIN_LANGUAGE_DIFF.patch for precise changes.
