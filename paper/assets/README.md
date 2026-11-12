# Paper build files

Everything `../main.tex` needs to build `../paper.pdf`.

- `supplement.tex`: supplementary material, included at the end of the paper
- `figures/`, `tables/`: figure assets and the replay table
- `declaration/`: the signed declaration appended to the end of the paper
- `font-maps.tex`, `vendor/`: bundled document class (`acmart`) and fonts for a self-contained build
- `latexmkrc`, `build.sh`: build configuration

## Build

From the `paper/` folder:

```sh
sh assets/build.sh
```

This runs `latexmk` with pdfLaTeX (two passes of `pdflatex` if `latexmk` is missing). The bibliography is inline, so no BibTeX or Biber run is needed. On Overleaf, upload the `paper/` folder, set the compiler to pdfLaTeX and the main document to `main.tex`; the bundled fonts are not needed there.
