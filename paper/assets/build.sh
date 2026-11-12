#!/bin/sh
# Builds ../paper.pdf from ../main.tex using the fonts and class bundled in assets/vendor.
cd -- "$(dirname -- "$0")/.." || exit 1
export TEXMFHOME="$PWD/assets/vendor/texmf"
if command -v latexmk >/dev/null 2>&1; then
    latexmk -r assets/latexmkrc -pdf -jobname=paper main.tex
else
    pdflatex -jobname=paper -interaction=nonstopmode -halt-on-error main.tex &&
    pdflatex -jobname=paper -interaction=nonstopmode -halt-on-error main.tex
fi
