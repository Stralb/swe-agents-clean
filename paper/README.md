# Paper

LaTeX source of the paper, with everything needed to build it.

- `main.tex`: manuscript, with the bibliography and some figures inline
- `supplement.tex`: supplementary material
- `figures/`, `tables/`: figure assets and the replay table
- `declaration/`: the signed declaration appended to the end of the paper
- `acmart.cls`, `vendor/`, `font-maps.tex`, `latexmkrc`, `build.sh`: document class and bundled fonts for a self-contained build
- `main.pdf`: rebuilt PDF; `submission.pdf`: the PDF as submitted

## Build

```sh
sh build.sh
```

This runs `latexmk` with pdfLaTeX (two passes of `pdflatex` if `latexmk` is missing). The bibliography is inline, so no BibTeX or Biber run is needed. On Overleaf, upload the folder, set the compiler to pdfLaTeX and the main document to `main.tex`.
