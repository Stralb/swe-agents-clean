# miner

Collects merged, issue-linked, agent-associated pull requests from GitHub and runs the scanners on them.

```bash
python -m miner init-db   # create or update the database
python -m miner collect   # find and store cases
python -m miner scan      # run the scanners on stored cases
python -m miner export    # write the case table
```

| Package | Role |
| --- | --- |
| `github/` | API client, rate limits, issue linking |
| `pipeline/` | Collection, case building, scanning and export |
| `filters/` | Pull request, issue and bot filters; scanner applicability |
| `markers/` | Agent-association markers |
| `scanners/` | CodeQL, Semgrep, OSV, Trivy, Gitleaks and the dependency diff |
| `artifacts/` | File type and region mapping |
| `workers/` | Scanner job queue |
| `db/` | SQLite access and schema |

Cases are stored in these tables:

![Case tables](../data/erd/mining.svg)

Configuration is read from `config.yml`; set `GITHUB_TOKEN` and `DB_PATH` in `.env` (see `.env.example`).
