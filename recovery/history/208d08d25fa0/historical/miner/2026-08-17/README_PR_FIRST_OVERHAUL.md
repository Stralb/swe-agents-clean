# PR-first downstream-evidence overhaul

This upgrade changes the miner toward the new methodology:

```text
repo/month window -> merged issue-linked PRs -> changed artifacts -> artifact regions -> scanner routes -> base/head introduced findings -> issue inspection later
```

## New principles

- Issue text and suspicious keywords are **features**, not inclusion gates.
- Candidate discovery starts from merged PRs linked to issues.
- Every changed file is classified into an artifact region; unknown machine-readable files are retained.
- Scanner routing is driven by artifact regions.
- Case status is synced from `scanner_jobs`, not stale historical `scanner_runs`.
- Region-yield reporting measures which artifact regions produce introduced downstream evidence.

## New commands

```bash
make methodology-profile      # classify changed files into artifact regions
make methodology-status       # resync case status from scanner_jobs + findings
make region-yield             # region-level yield report
make collect-pr-first          # PR-first collection mode, no suspicious keyword gate
make slurm-pr-first            # submit PR-first collection as a Slurm job
make slurm-evaluate-cheap      # submit cheap scanners as a Slurm job
make slurm-evaluate-codeql     # submit CodeQL as a Slurm job with Go pack download + safer caches
make slurm-status              # submit status/yield report as a Slurm job
```

## Recommended cluster flow

```bash
cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart
source .venv/bin/activate
source .env.cluster

make init-db
make slurm-pr-first
squeue -u "$USER"

make slurm-evaluate-cheap
make slurm-evaluate-codeql
make methodology-profile
make methodology-status
make region-yield
make ui
```

## New tables

- `artifact_regions`: one row per changed file with region, language, generated/vendor flags, scanner routes, and evidence.
- `pr_region_profiles`: one row per case with primary region, region counts, scanner routes, languages, and file count.

## Tests added

```bash
PYTHONPATH=. pytest -q tests/test_artifact_regions_methodology.py tests/test_case_status_sync.py
```


## Optional artifact profiling/security tools

Install user-space helper tools on the cluster:

```bash
cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart
source .venv/bin/activate
make install-cluster-tools
make tools STRICT_TOOLS=false
```

Tool roles:

| Tool | Role in the methodology |
|---|---|
| `identify-cli` | Mechanical file tags: text, binary, executable, symlink, language-ish tags |
| `github-linguist` | GitHub-style language plus generated/vendor/binary classification where available |
| `trivy` | Cheap broad base/head signal for vulnerabilities, secrets, and misconfiguration |

The miner treats these as profiling/routing helpers. Missing optional tools should not make collection fail; they should degrade to filename and extension heuristics.

## GitHub tokens

Do not hard-code GitHub tokens into `Makefile` or source code. Put them in `.env.cluster`, which should not be committed:

```bash
GITHUB_TOKENS=token_from_account_1,token_from_account_2
```

The GitHub client accepts `GITHUB_TOKENS`, `GITHUB_TOKEN`, or `GH_TOKEN`. When multiple tokens are supplied, it rotates to the next token if one is rejected or hits primary rate limit pressure.
