#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
export TEXMFHOME="$PWD/vendor/texmf"
if command -v latexmk >/dev/null 2>&1; then
    latexmk -r latexmkrc -pdf main.tex
else
    pdflatex -interaction=nonstopmode -halt-on-error main.tex &&
    pdflatex -interaction=nonstopmode -halt-on-error main.tex
fi
