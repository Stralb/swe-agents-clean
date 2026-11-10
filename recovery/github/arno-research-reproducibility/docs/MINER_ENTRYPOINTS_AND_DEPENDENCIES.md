# Miner recovery: entrypoints, dependencies and promotion boundaries

**Source basis:** SHA-256-registered October 20 live Wits miner TAR and August 17/19 source snapshots. This is **static source inspection only**; no historical entrypoint was executed.

## Executable topology of the live miner

```text
src/main.py (guarded CLI)
  |-- src.settings.load_settings()
  |-- src.pipeline.collect_pipeline.collect()
  |    |-- src.github.client / rate_limit / issue_linker
  |    |-- src.filters (bot, issue, PR, applicability)
  |    |-- src.markers (AI markers, upstream features)
  |    `-- src.db.database.Database
  `-- src.pipeline.scan_pipeline.scan()
       |-- src.workers.job_queue
       |-- src.scanners.scanner_runner
       |    `-- CodeQL / Semgrep / OSV / Gitleaks / Trivy / dependency diff
       `-- src.db.database.Database

scripts/workers.py -> src.workers.supervisor -> evaluator / job_queue
src.distributed.local_coordinator -> mining / cheap / CodeQL pipelines
  `-- spool, pool control, UI commands, shared database
ui/app.py -> views, database, case exports, overview and analytics
analysis/full_corpus_discovery_v1_1/ -> separate archived analysis
analysis/full_corpus_deep_discovery_v2/ -> separate archived analysis
```

The diagram lists imports and observed call direction, not a guaranteed full runtime dataflow. Exact scanner availability, queue concurrency, settings and runtime behavior require isolated testing.

## Specific original entrypoints

| Path in live archive | Observed action | Recovery status |
| --- | --- | --- |
| `src/main.py` | Calls `collect(settings)` and then `scan(settings)` under a main guard | Historical, mutating; do not run |
| `scripts/collect.py` | Calls `collect(load_settings())` **at module import time** | Historical, unsafe to import |
| `scripts/scan.py` | Calls `scan(load_settings())` **at module import time** | Historical, unsafe to import |
| `scripts/workers.py` | Imports `src.workers.supervisor.main`; protected by main guard | Historical; worker runtime writes DB/job states |
| `scripts/cluster_run.py` | Builds cluster commands; embeds Wits working-directory and activation paths | Historical, cluster-specific |
| `src/distributed/local_coordinator.py` | Uses a hard-coded Wits directory and coordinator/spool/database modules | Historical, potentially destructive on original datasets |
| `ui/app.py` | Sets Streamlit UI flags, resolves live DB pointer and imports view/database/export modules | Historical, runtime-dependent |
| `analysis/full_corpus_discovery_v1_1/discovery.py` | Imports numerical/statistical stack; independent analysis stages | Historical; do not run against existing outputs |

## Packages and external binaries

`requirements.txt` expresses **lower bounds**, not a reproducible lock. Listed Python packages include Requests, PyYAML, python-dotenv, Streamlit, pandas, langdetect, packaging, rich and Semgrep. Other stages import packages such as NumPy/SciPy/scikit-learn not fully captured by the base miner requirements file. Scanner execution additionally requires tool-specific binaries and query packs (CodeQL, Trivy, Gitleaks, etc.); archive presence alone does not prove availability or matching versions.

## Source layout and version forks

- The August 17, August 19 and live snapshots share the same core scanner modules; an existing SHA-256 comparison identifies their exact divergences.
- The August 19 review UI has additional view/review files absent in the live snapshot and must remain a **distinct historical variant**.
- The live coordinator uses a shared database path in a code path that differs from August versions. Do not use it against the frozen database.
- The live `backups/` tree supplies 276 code-like historical snapshots for possible chronological reconstruction; its bulk JSON/log data is **not** executable source and remains outside Git.
- Discovery v2.1/v2.2 and October job drivers are separate directories; they must not be merged into the miner package merely because a later file exists.

## Promotion checklist (engineering only)

1. Record the original file/ZIP SHA-256 and exact source member path.
2. Identify the explicit entrypoint, direct imports, runtime files, environment variables and external tool requirements.
3. Distinguish source modules safe to import from scripts that execute at import-time.
4. Identify and remove or isolate hard-coded historical filesystem paths **only in new candidate code**, never by editing the archived version.
5. Test on synthetic fixtures or new disposable workspaces; original Wits databases and outputs remain immutable.
6. Promote tested code into a separate active module with an explicit attribution/correction record.
7. Leave failed and superseded scripts under their original `historical/` paths.

**Status:** topology mapped by source inspection. Active implementation reconstruction is pending the source snapshot import and isolation tests.
