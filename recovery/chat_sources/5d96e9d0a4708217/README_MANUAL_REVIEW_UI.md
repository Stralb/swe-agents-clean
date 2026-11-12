# Manual Review Research UI

This Streamlit mode is the research-review instrument for the static-analysis-positive cohort.

## Purpose

The immutable Hugging Face Parquet snapshot supplies the mined GitHub cases and scanner evidence. The UI then derives, locally and deterministically:

- canonical security events that collapse redundant scanner reports;
- finding-to-PR attribution using changed files, dependency evidence, and CodeQL flows;
- an evidence-family/archetype for each positive case;
- a review-priority heuristic based on attribution quality, not predicted maliciousness.

The researcher manually assigns the final study taxonomy:

- maliciousness level;
- likely malicious intent;
- issue disguise/framing;
- confidence;
- rationale and technical notes.

Manual labels are stored in `data/manual_review.sqlite3` by default. This file is ignored by git. The UI can export all manual labels as CSV for backup and analysis.

## Local setup

Authenticate to Hugging Face once:

```bash
hf auth login
```

Install dependencies and run:

```bash
python -m pip install -r requirements.txt
UI_DATA_BACKEND=parquet python -m streamlit run ui/app.py
```

On Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
$env:UI_DATA_BACKEND="parquet"
python -m streamlit run ui/app.py
```

## Supervisor demo path

1. **Study Overview** — show the full candidate-to-manual-review funnel and current review progress.
2. **Evidence Insights** — show scanner redundancy, canonical events, evidence families, attribution quality, and why raw scanner counts are not treated as maliciousness.
3. **Manual Review** — open a positive case, inspect the causal static-analysis evidence, then assign the manual taxonomy and use **Save + next case**.
4. **Methodology** — show the explicit separation between candidate selection, introduced static-analysis evidence, PR attribution, and manual maliciousness judgement.

## Important interpretation

A static-analysis positive is not automatically malicious. The scanner signal narrows the candidate set. The final research judgement comes from manual review of the issue request, resulting PR, introduced security effect, attribution quality, and contextual evidence.
