# MATCHED_CONTROL_C3_v1.0

C3 extracts evidence for the frozen 190 scanner-negative controls selected in C2. It performs no semantic classification.

Blindness order:
1. `01_ISSUE_BLIND/` — issue title/body only.
2. Freeze issue summaries/categories.
3. `02_PR_BLIND/` — PR title/body only.
4. Freeze PR summaries/categories/alignment.
5. `03_IMPLEMENTATION_BLIND/` — changed-file metadata + bounded patch evidence only.
6. Freeze implementation summaries/categories.
7. `04_CONTEXT_SEPARATE/` — factual timing/author/provenance/review rows, only after semantic stages are frozen.

`90_LOCKED_MATCHING/` contains the C2 positive↔control mapping and must remain hidden during annotation.

Full raw diff evidence is retained under `03_IMPLEMENTATION_FULL_RAW/`; deterministic bounded packets are used for annotation so large lockfiles/generated artifacts cannot dominate model context.
