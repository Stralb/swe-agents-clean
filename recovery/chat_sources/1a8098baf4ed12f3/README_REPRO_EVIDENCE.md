# A24 revision: V6 scanner evidence and evaluation protocols

Build: `latexmk -pdf -interaction=nonstopmode main.tex`.

This revision starts from the latest Table S9-corrected, supplement-cleaned A24 source. It changes only Section 8's last sentence and adds Supplementary Exhibit S7 plus reproducibility text files. No reported results or counts were changed.

## Reproducibility files

- `reproducibility/SCANNER_RUNTIME_RECORD.md` -- archived scanner versions and config, with exact V6 path pointers and observation scopes.
- `reproducibility/PROMPTS_AND_EVALUATION_PROTOCOLS.md` -- recovered verbatim prompt and frozen protocols with explicit provenance labels.
- `reproducibility/STAGE4B_PROMPT_VERBATIM.txt` -- the exact frozen Stage 4B text.

The `.env.cluster` contents are not exposed by the V6 artifact-read interface used in this review. We did not print or include secrets; values inferred from source defaults are distinguished from observed runtime logs. Tool version observations do not prove that the entire corpus used one unchanging toolchain.
