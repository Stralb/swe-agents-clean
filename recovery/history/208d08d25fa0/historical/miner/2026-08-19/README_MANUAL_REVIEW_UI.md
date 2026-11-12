# Manual Review Research UI

The Parquet Streamlit mode is the manual research instrument for the static-analysis-positive cohort.

## Current study workflow

The UI deliberately separates each case into three stages:

1. **Upstream** - what the original issue asked for, which exact downstream entities it names, simple technical/review wording cues, and the author/PR context already stored in the snapshot.
2. **Downstream** - the introduced static-analysis events, PR attribution, changed files, scanner flags attached to each file, CodeQL flow links, and the actual patch/diff.
3. **Decision** - the human judgement about how the issue request relates to the security-relevant change and the final research taxonomy.

The static-analysis positive is not itself a maliciousness label. The automated pipeline finds cases worth reading; the human reviewer decides whether the evidence is malicious, suspicious, benign, an attribution artifact, or insufficient.

## What is derived without extra GitHub enrichment

The current snapshot already supports the immediate supervisor-facing analysis:

- original issue title/body and issue author;
- PR author, state, merge state, timestamps, changed lines, changed files, commits;
- deterministic issue-to-change overlap for exact affected packages, versions, changed/finding files, and vulnerability IDs;
- technical issue wording and a small set of review cues such as downgrade/disable/bypass wording;
- canonical security events that collapse duplicate scanner reports;
- finding-to-PR attribution using changed files, dependency evidence, and CodeQL flows;
- changed-file patches and scanner findings connected to each file;
- manual labels and rationale stored locally.

The **Study Overview**, **Manual Review**, and **Evidence Insights** pages can export a CSV summarising the upstream findings for the full static-analysis-positive cohort.

## Optional later enrichment

Do not block the current review on these. They are not present in the current snapshot and require new GitHub API collection:

- GitHub account creation date / account age;
- author association (owner/member/contributor/first-time contributor) if not recoverable from existing raw responses;
- prior issues/PRs in the repository and historical merge/close rates;
- maintainer review text and rejection/revert reasons;
- richer author history across GitHub.

These can be added later if the first manual pass suggests they would materially help distinguish cases.

## Manual decision fields

The decision tab records:

- issue-to-security-change connection;
- whether the security effect is aligned with, incidental to, or conflicts with the stated issue goal;
- plausibility of a benign explanation;
- maliciousness level;
- likely intent;
- issue disguise/framing;
- confidence;
- rationale and technical notes.

Manual labels are stored in `data/manual_review.sqlite3` by default. The database is git-ignored and is migrated automatically when new decision fields are added.

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

Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
$env:UI_DATA_BACKEND="parquet"
python -m streamlit run ui/app.py
```

## Supervisor demo path

1. **Study Overview** - show the candidate funnel and export the 138-case upstream findings CSV.
2. **Evidence Insights** - show issue-to-change overlap, PR size, scanner redundancy, evidence families, and attribution quality.
3. **Manual Review** - open one case and move through **Upstream -> Downstream -> Decision**.
4. In **Downstream**, select a changed file to show its scanner flags and load the actual diff.
5. In **Decision**, save the structured manual assessment and use **Save + next case**.
