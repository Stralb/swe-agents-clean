# Arno A24 manuscript — layout revision (9 November 2026)

This directory contains the editable ACM Small paper and supplementary material.

## Build

From this directory, with a TeX Live installation containing `acmart`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

Main document: `main.tex`. Supplement: `supplement.tex`. Other inputs are in `figures/`, `tables/`, and `reproducibility/`.

## This revision

- Removed the colon in the manuscript title and placed the explanatory subtitle on a new line. PDF metadata now has a clean textual title.
- Explicitly starts **References** on a new page, and uses a restrained 8 pt / 9 pt bibliography setting to keep all references on one page.
- Removed the near-empty spillover page by shortening only the Data and Code Availability wording while retaining the repository address and distinction between the 122-instance workbook and later archives.
- Disabled forced page-height stretching in the supplement and normalised spacing around in-text tables and fixed evidence blocks; unbreakable case evidence is kept intact when a page ends.
- Changed case-card headings to ragged-right composition to avoid expanded interword spacing.
- Normalised S7 as a numbered supplementary section, matching S1--S6.

No research counts, case facts, scanner findings, statistical tests, or experiment conclusions were altered.

The paper uses the original figure assets. The uploaded figure crop was consulted when reviewing the layout, but the internal diagram was not redrawn as no figure-content change was requested.
