# Issue-to-PR Security Analysis

Research code for examining scanner-reported security findings in GitHub pull requests associated with coding agents.

The repository includes the original mining and scanning implementation, a review interface, and the analysis code for the matched workflow study.

## Code

| Location | Purpose |
| --- | --- |
| [`src/`](src/) | GitHub collection, issue linking, filters, scanners, database, and workers |
| [`scripts/`](scripts/) | Collection, scanning, exports, and verification commands |
| [`analysis/`](analysis/) | Cohort checks, matched comparisons, scanner evidence, and root crosswalks |
| [`data/`](data/) | Aggregate paired tables and source-recorded validation inputs |
| [`ui/`](ui/) | Case review and inspection interface |
| [`tests/`](tests/) | Miner and analysis tests |

The original miner entrypoints are in `src/main.py` and `scripts/`. Configuration is in `config.yml` and `config.agentic_js.yml`.

## Check the analysis

Run from the repository root:

```bash
python3 -m analysis.reproduce_matched --check
python3 -m analysis.cluster_stage_lineage audit-recorded
python3 -m unittest discover -s tests -p 'test_reproduce_matched.py' -v
```

These checks use included aggregate data. They do not rerun GitHub collection or the original scanner jobs. For the original mining commands, run `make help` and inspect the configuration before connecting to any external service.

## Research notes

- [Methods and results](docs/methods.md)
- [Reproducing the analysis](docs/reproducibility.md)

Original case-level data, scanner baselines, and exact historical tool environments are not included. A scanner warning is an observed finding, not proof of an exploitable vulnerability.
