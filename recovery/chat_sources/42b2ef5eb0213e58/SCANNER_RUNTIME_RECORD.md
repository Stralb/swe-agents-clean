# Scanner runtime and configuration evidence (V6)

Checked: 2026-11-09. This file records *observations*, not a global pinned scanner lockfile. No credentials or other secrets are included.

## Version observations

| Scanner/asset | Observed version or value | Concrete evidence | Scope |
|---|---|---|---|
| CodeQL CLI | `2.25.6` | `counterfactual_replay_r1/exact_historical_env_3581/out.txt` (`codeql version`) | Historical-environment replay; not a verified claim for all 3,809 original scans |
| JavaScript CodeQL query pack | `codeql/javascript-queries/2.3.11` | Original July scanner-run `stderr` in `miner.agentic-js.eval.20260720_224159.db`; also `counterfactual_replay_r1/codeql_historical_code_3581/result.txt` | Original scans show this pack path; check per-run for universal claim |
| Trivy CLI | `0.72.0` | Original `scanner_runs` record for `scanner='trivy-scanner'`, captured `stdout.trivy_version` | Confirmed in inspected original July runs |
| Trivy vulnerability DB | format version `2`; `UpdatedAt 2026-07-22 13:17:28 UTC` | Same original `scanner_runs.stdout` | One archived database snapshot observation, not a guarantee of a pinned global DB |
| Semgrep | executable version not established | Recovered config says `semgrep_config: p/security-audit`; `semgrep` original runs exist | Configured ruleset only; do not infer an exact CLI version from `requirements.txt` |
| OSV-Scanner | executable version not established | `osv-scanner` original runs; recovered `src/scanners/osv_scanner.py` invokes `osv-scanner scan --format ...` | Live vulnerability lookup/data may depend on date |
| Gitleaks | executable version not established | `gitleaks` original run records and `src/scanners/gitleaks_scanner.py` | Exact CLI version absent from inspected output |
| Dependency downgrade | internal checker | V6 config `dependency_downgrade: true`; GitHub recovered source | Not a separate versioned binary |

## Configuration observations (distinguish source defaults vs cluster run)

- The recovered project config `config.agentic_javascript.yml` enables CodeQL, Semgrep, Trivy, OSV-Scanner, Gitleaks and dependency-downgrade checks.
- It selects `codeql_language: auto`, `codeql_build_mode: none`, `codeql_query_suite: null` (resolved by worker defaults), and `semgrep_config: p/security-audit`.
- The recovered CodeQL scanner's default JavaScript suite is `codeql/javascript-queries:codeql-suites/javascript-security-extended.qls`.
- The actual V6 historical-environment replay `counterfactual_replay_r1/exact_historical_env_3581/run.sbatch` explicitly uses that JavaScript suite, `language=javascript-typescript`, `build_mode=none`, timeout 1,800s.
- That replay exports `CODEQL_RAM_MB=12000`, `CODEQL_THREADS=2`, `CODEQL_TMPDIR=/tmp/$USER/codeql-$SLURM_JOB_ID`, and `MINER_CODEQL_TMPDIR=$CODEQL_TMPDIR`. These are replay-stage settings; historical corpus-wide equality is not established.
- The original full-corpus completion worker `full3809_scan_completion/full3809_codeql_worker.sbatch` loads `.env.cluster` then sets `CONFIG=$ROOT/config.agentic_js.yml`, `PYTHONPATH`, and per-job temporary/spool directory variables. V6's restricted artefact-read API cannot read `.env.cluster` directly. The names and *non-secret* values above are not a verified dump of that file.
- Trivy implementation invokes `trivy fs` with vulnerability-only scanning, JSON output and `--offline-scan`; tool version and DB time were captured by the scanner.
- Semgrep's registry ruleset `p/security-audit` is a rule bundle identifier, not a frozen rule digest.

## How to retrieve read-only version data on the actual cluster (not executed by this extract)

From a trusted SSH shell on the research host, inside the historical environment, these commands display scanner versions without dumping tokens:

```bash
codeql version
codeql resolve packs
trivy --version
semgrep --version
osv-scanner --version
gitleaks version
```

The current output of these commands would describe the environment **at that later time**; the original `scanner_runs` records are needed to link a version or advisory DB to each historical scan.

## Provenance paths

V6: `~/research_artifacts/counterfactual_replay_r1/exact_historical_env_3581/out.txt`;
`~/research_artifacts/counterfactual_replay_r1/exact_historical_env_3581/run.sbatch`;
`~/research_artifacts/full3809_scan_completion/full3809_codeql_worker.sbatch`;
miner DB `~/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.db`.

Connected recovered GitHub repository: `Stralb/adversarial-swe-agents`, files `config.agentic_javascript.yml`, `src/scanners/codeql_scanner.py`, `src/scanners/semgrep_scanner.py`, `src/scanners/trivy_scanner.py`, `src/scanners/osv_scanner.py`, `src/scanners/gitleaks_scanner.py` and `docs/reproducibility.md`.

Note: the connected GitHub repository documents that recovered miner source is not proven byte-identical to code used for every original scan. Preserve this qualification; do not imply otherwise.
