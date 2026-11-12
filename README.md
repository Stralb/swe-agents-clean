# Security findings in agent-associated pull requests

Code and analysis for an observational study of GitHub issues and pull requests associated with coding agents. The study examines scanner-reported findings in the resulting changes and compares the affected workflows with matched controls.

**Status:** Research in progress. The included aggregates can be checked offline, but the full historical study cannot yet be reproduced from this repository alone.

**Dataset:** [Hugging Face — adversarial-swe-agents](https://huggingface.co/datasets/Stralb/adversarial-swe-agents) *(private access required)*. The default `paper_cases` configuration contains 3,809 cases with explicit flags for the 192 finding-positive cases. [Pinned data revision](https://huggingface.co/datasets/Stralb/adversarial-swe-agents/tree/e71e8b39ed56ffb1c2198b9df2384495b8404317) · [Dataset guide and verification](dataset/README.md).

**Database filename:** `adversarial-swe-agents.sqlite`.

## Repository

| Directory | Contents |
| --- | --- |
| `src/` | Collection, issue linking, filters, scanners, database, and workers |
| `scripts/` | Commands for collecting, scanning, exporting, and checking cases |
| `analysis/` | Cohort checks, paired comparisons, and source-data verification |
| `data/` | Aggregate results and recorded cohort metadata |
| `ui/` | Case inspection interface |
| `paper/` | Current ACM Small manuscript source and compiled PDF |
| `tests/` | Miner and analysis tests |
| `literature/` | Earlier reading notes and literature review, not the current manuscript |

## Check the results

Use Python 3.11 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
make setup
make check
```

`make check` checks Python syntax, recalculates the available aggregate paired tests, checks recorded cohort totals, and runs a selected set of miner tests. It does not access GitHub, launch scanners, or modify research data.

To inspect the paired results directly:

```bash
python3 -m analysis.matched_results --check
```

## Manuscript

The current research draft is in [`paper/main.tex`](paper/main.tex), with a [compiled PDF](paper/main.pdf) committed alongside it. The LaTeX file contains the complete text, methodology figure, and bibliography.

To rebuild the PDF locally with the ACM class and `latexmk` installed:

```bash
cd paper
latexmk -pdf main.tex
```

In Overleaf, set `paper/main.tex` as the main document. Generated LaTeX intermediate files are not tracked.

## Running the miner

The miner is separate from the offline checks. Set up a local environment before collecting cases:

```bash
cp .env.example .env
# Set GITHUB_TOKEN and inspect CONFIG and DB_PATH in .env
make install
```

Collection requires GitHub credentials, a writable local database, and a deliberately selected configuration. The included JavaScript configuration reflects the historical study setup, not a safe small test run. Check its scope and limits before using it.

Inspect `src/settings.py` and set `DB_PATH` to a disposable location before using `make collect` or `make scan`. These commands write to the database. External scanners must be installed separately. The recovered cluster-specific code is not a ready-to-run deployment.

## Study and limitations

The recorded population comprises 3,809 linked workflows, including 192 scanner-positive workflows. The matched analysis uses 190 pairs, of which 115 share a repository. These are source-recorded counts, not newly reconstructed outcomes.

A scanner finding is not proof of an exploitable vulnerability or a malicious issue. Matching also does not establish causality.

See [methods and results](docs/methods.md) and [reproduction notes](docs/reproducibility.md) for exactly what has been checked and what remains unavailable.

## Research dataset

Start with [the dataset guide](dataset/README.md) for case membership, evidence links, schema and access. The Parquet release is uploaded and verified; the guide records its pinned data revision and the separate SQLite preparation status. Historical sources remain under `recovery/` and on the `preservation/20261111` branch.
