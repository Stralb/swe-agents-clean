#!/bin/bash
#SBATCH --job-name=cf_oldql
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_historical_code_3581/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_historical_code_3581/error.txt

set -u

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$MINER"

source .venv/bin/activate
[ -f .env.cluster ] && source .env.cluster

export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"

echo "=== CURRENT SOURCE ==="
echo "HEAD=$(git rev-parse HEAD)"

OLD="$(git rev-list -1 --before='2026-07-25T11:52:35Z' HEAD)"

echo
echo "=== HISTORICAL COMMIT ==="
echo "OLD=$OLD"
git show -s --format='%H %ci %s' "$OLD"

echo
echo "=== SCANNER CODE CHANGES SINCE HISTORICAL COMMIT ==="
git diff --stat "$OLD" HEAD -- \
  src/scanners/codeql_scanner.py \
  src/distributed/codeql_pipeline.py

echo
echo "=== RELEVANT CODE DIFF ==="
git diff "$OLD" HEAD -- \
  src/scanners/codeql_scanner.py \
  src/distributed/codeql_pipeline.py | \
  grep -E '^[+-].*(database|db_|tmp|temp|cache|sarif|source|checkout|clone|create|analyze|query|codeql)' | \
  head -200

TMP="$(mktemp -d)"
mkdir -p "$TMP/old"

git archive "$OLD" | tar -x -C "$TMP/old"

echo
echo "=== RUN HISTORICAL SCANNER CODE ==="

PYTHONPATH="$TMP/old" python3 - <<'PY'
from src.scanners.codeql_scanner import scan_snapshot_with_codeql
import inspect

print("SIGNATURE", inspect.signature(scan_snapshot_with_codeql))

findings, meta = scan_snapshot_with_codeql(
    repo_url="https://github.com/breaking-brake/cc-wf-studio.git",
    sha="bb7ddadd4e17c9ace31ed2e3a59eb8e3070150ee",
    language="javascript-typescript",
    build_mode="none",
    query_suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
    timeout_seconds=1800,
)

print("STATUS", meta.get("status"))
print("TOTAL", len(findings))

for rule in ("js/file-system-race", "js/missing-origin-check"):
    hits = [
        f for f in findings
        if (f.get("rule_id") or f.get("ruleId")) == rule
    ]
    print(rule, len(hits))
    for h in hits:
        print(h)
PY

echo
echo "=== TOOL FILE DATES ==="
stat -c '%y %n' \
 "$HOME/tools/codeql/codeql" \
 "$HOME/tools/node/bin/node" \
 "$HOME/.codeql/packages/codeql/javascript-queries/2.3.11/Security/CWE-367/FileSystemRace.ql" \
 "$HOME/.codeql/packages/codeql/javascript-queries/2.3.11/Security/CWE-346/MissingOriginCheck.ql" \
 2>/dev/null

rm -rf "$TMP"
