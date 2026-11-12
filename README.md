# Security findings in agent-associated pull requests

Code and analysis for an observational study of GitHub issues and pull requests associated with coding agents. The study traces scanner-reported findings in the resulting changes back to the changed operations responsible for them, and compares the affected workflows with matched controls.

**Paper:** [paper/main.pdf](paper/main.pdf)
**Dataset:** [Hugging Face](https://huggingface.co/datasets/Stralb/adversarial-swe-agents) *(private access required)* · [dataset guide](dataset/README.md)
**Archive (DOI):** *to be added*

## Quick start

Python 3.11 or later. No GitHub token and no scanners are needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
make setup
make check
```

`make check` checks Python syntax, recalculates the available paired tests from the bundled aggregates, checks the recorded cohort totals, and runs a selected set of miner tests. It does not access GitHub, launch scanners, or modify research data.

## Contents

| Path | Contents |
| --- | --- |
| `src/` | Collection, issue linking, filters, scanners, database, and workers |
| `scripts/` | Commands for collecting, scanning, exporting, and checking cases |
| `analysis/` | Cohort checks, paired comparisons, and source-data verification |
| `data/` | Aggregate results and recorded cohort metadata |
| `dataset/` | Dataset documentation, schema and build scripts |
| `experiments/rq3/` | Scripts behind the RQ3 O/W/P CodeQL replay comparison ([details](experiments/rq3/README.md)) |
| `docs/` | [Methods and results](docs/methods.md) · [reproduction notes](docs/reproducibility.md) |
| `paper/` | Manuscript source and compiled PDF |
| `tests/` | Miner and analysis tests |

## Study at a glance

The recorded population is 3,809 linked issue-to-pull-request workflows, of which 192 are scanner-positive. The matched analysis uses 190 pairs, 115 of them within the same repository. These are source-recorded counts. A scanner finding is not proof of an exploitable vulnerability or of a malicious issue, and matching does not establish causality.

## Not included

The original frozen database, scanner outputs, query packs and runtime environment are not part of this repository, so the full historical study cannot be reproduced from it alone. Case-level data is released through the dataset above. See [docs/reproducibility.md](docs/reproducibility.md) for exactly what has been checked and what remains unavailable.

## Running the miner (optional)

Collection needs GitHub credentials, a writable local database and externally installed scanners, and it writes data. Use a disposable database.

```bash
cp .env.example .env
# set GITHUB_TOKEN; inspect CONFIG and DB_PATH
make install
```

`config.agentic_javascript.yml` reflects the historical study setup, not a safe small test run. Check its scope and limits first, and set `DB_PATH` to a disposable location before `make collect` or `make scan`.

## Citation

See [CITATION.cff](CITATION.cff).

## License

Code is released under the [MIT License](LICENSE).
