# Research manuscript editorial revision - 9 November 2026

The canonical manuscript source is `main.tex`, with `supplement.tex` imported at the end. Build with:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The compiled paper is `main.pdf`. The appendix has Sections S1-S6; the scanner and evaluation evidence formerly in S7 was previously integrated into Table S2 and Section S2.

See `FINAL_USER_REQUEST_CHANGELOG.md` and the accompanying manuscript diff for editorial changes. This revision did not recompute study results.
