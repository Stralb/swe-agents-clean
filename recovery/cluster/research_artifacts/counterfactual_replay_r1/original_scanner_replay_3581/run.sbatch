#!/bin/bash
#SBATCH --job-name=cf_orig3581
#SBATCH --partition=batch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/original_scanner_replay_3581/job.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/original_scanner_replay_3581/job.err

set -euo pipefail

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$MINER"

export PATH="/home-mscluster/astrauss/tools/codeql:$PATH"
export PYTHONPATH="$MINER"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 - <<'PY'
from src.scanners.codeql_scanner import scan_snapshot_with_codeql, default_query_suite_for_language

repo = "https://github.com/breaking-brake/cc-wf-studio.git"
sha = "bb7ddadd4e17c9ace31ed2e3a59eb8e3070150ee"
lang = "javascript-typescript"

suite = default_query_suite_for_language(lang)
print("SUITE=", suite)

findings, meta = scan_snapshot_with_codeql(
    repo_url=repo,
    sha=sha,
    language=lang,
    build_mode="none",
    query_suite=suite,
    timeout_seconds=1800,
)

print("STATUS=", meta.get("status"))
print("TOTAL_FINDINGS=", len(findings))

targets = {"js/file-system-race", "js/missing-origin-check"}

for f in findings:
    rid = f.get("rule_id") or f.get("ruleId")
    if rid in targets:
        print(
            "TARGET",
            rid,
            f.get("file_path") or f.get("path"),
            f.get("line"),
            f.get("description") or f.get("message"),
        )

print("TARGET_COUNTS=")
for rid in sorted(targets):
    n = sum(
        1 for f in findings
        if (f.get("rule_id") or f.get("ruleId")) == rid
    )
    print(rid, n)
PY
