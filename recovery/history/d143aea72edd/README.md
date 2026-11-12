# Research source code — supervisor review (23 October 2026)

**This is a code-first repository snapshot.** The original ten-file branch was insufficient because it did not include the mining, scanning and analysis implementation. The source files below are copied **byte-for-byte from existing Git blobs** in `work/miner-core-consolidation-20261021` (source tree `7e9c176c5d4f300826143f19d65e37fa95010cf2`); they have not been rewritten to fit the reported results.

## Start with the code

| Directory | What it contains |
|---|---|
| [`miner/src/`](miner/src/) | Original recovered GitHub issue/PR mining, filtering, AI markers, scanner attribution, database and worker implementation |
| [`miner/scripts/`](miner/scripts/) and [`miner/tests/`](miner/tests/) | Miner commands, case exports, revalidation and original tests |
| [`miner/config.agentic_js.yml`](miner/config.agentic_js.yml) | Saved multi-language agent-associated collection/scanner configuration |
| [`miner-original-aug17/`](miner-original-aug17/) | Earlier complete miner source candidate, preserved separately to expose version differences |
| [`analysis/`](analysis/) | Matched-control C1/C2/C6/C7 computations, paired tests and provenance/root/chronology audit programs |
| [`discovery/`](discovery/) | Outcome-blind whole-corpus discovery v2.1/v2.2 implementations and cluster launch scripts |
| [`controls/`](controls/) | Historical decision-level matched-control evidence collector |
| [`experiments/october/`](experiments/october/) | Historical October experiment/replay/evaluation scripts and Slurm jobs |
| [`scripts/reproduce_matched.py`](scripts/reproduce_matched.py) | Independent aggregate **test-formula** replay supplied in this branch (not full source-data reproduction) |

## Source and reproduction boundaries

- `miner/` is the **20 October recovered live source candidate**, not an authenticated claim that these exact bytes produced every historical scanner result. The dated August version is preserved alongside it. The underlying original frozen SQLite corpus, exact scanner binaries/query packs, historical raw SARIF and some original case-label/adjudication artifacts are **not included**.
- The `analysis/` files largely contain later independent verification/recovery code. Do **not** represent all of them as the original scripts used to generate the frozen C6 or D labels; those original source identities still require reconciliation.
- The experimental scripts are **historical**, not endorsed as independently reproduced effects. Replaying them requires the historical frozen pre-PR repositories, inputs, model configuration and exact scanner installation.
- No credentials or live database are included. Do not run miner jobs against the original Wits cluster, database or external GitHub API from this branch without deliberately configuring a separate environment.

## Basic local checks

From repository root:

```bash
python3 scripts/reproduce_matched.py --check
python3 -m unittest discover -s tests -v
```

Those tests check aggregate calculations. Original miner dependencies and execution entrypoints are in [`miner/requirements.txt`](miner/requirements.txt), [`miner/Makefile`](miner/Makefile), and [`miner/README.md`](miner/README.md). Scanner engines are external executables.

This branch is private and **shares its Git history and access control with the parent repository**. To give someone access only to these working-tree files, export a ZIP or commit them into a new isolated repository; creating a branch alone does not restrict access to the rest of the original repository.
