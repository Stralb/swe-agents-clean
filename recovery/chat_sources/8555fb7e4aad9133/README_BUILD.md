# Building the reviewed manuscript

Open `main.tex` as the root document and compile with pdfLaTeX.

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The package contains the full manuscript, supplementary material, replay table, all original figure PDFs, the bibliography embedded in `main.tex`, and the accompanying reproducibility records. Keep the directory structure intact.

`acmart.cls` version 2.21 and its corresponding `acmart.dtx` are included. A standard current TeX Live or MiKTeX installation with ACM support is recommended. Required font packages include `libertine`, `inconsolata` (`zi4`) and `newtx`; `newtx` also uses `binhex` from the `kastrup` package. The other required packages are listed in the preamble. Overleaf's full TeX Live installation normally supplies these dependencies.

`main.pdf` is the checked output. `CHANGELOG_PRE_SUBMISSION.txt` describes this targeted correction pass. `REMAINING_ISSUES.txt` lists evidence limitations that could not be resolved from the supplied records. `TARGETED_CORRECTIONS.patch` records the text changes against the REVIEWED manuscript. Earlier notes and patches are historical records.

The bibliography has the same 23 entries as the REVIEWED version. The source under `archival/` preserves the original secondary replay material, removed case-summary table and preceding figure versions. Those LaTeX excerpts are retained records, not standalone documents and not included by the main manuscript. In particular, the P1-P5 comparison is excluded from the submitted PDF. The retained O/W/P results are unchanged.

Figure S1 is restored with all three original panels, full legends and unchanged percentages. The caption identifies the known README file-type discrepancy and the uncertain origin-panel version. The documentation-label correction is recorded in `reproducibility/CLASSIFICATION_CORRECTIONS.csv`.

The original Fig1_Conceptual.pdf is restored as Figure 1 alongside the retained compact conceptual Figure 2. See FIGURE_RESTORATION.txt.

Latest figure update: Figure S1 is restored in full with its original three panels and complete legends. Its caption discloses the known historical classification limits. The previous panel-removal notes describe the preceding pass. FINAL_FIGURE_CHECK.txt records this update and the two typo checks. The original Figure 1 and new Figure 2 are both retained.
