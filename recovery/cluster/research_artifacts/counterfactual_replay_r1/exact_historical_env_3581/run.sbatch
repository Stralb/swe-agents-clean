#!/bin/bash
#SBATCH --job-name=cf_hist3581
#SBATCH --partition=batch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/exact_historical_env_3581/out.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/exact_historical_env_3581/err.txt

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$MINER"

source .venv/bin/activate
[ -f .env.cluster ] && source .env.cluster

export PYTHONPATH="$MINER"
export PATH="$HOME/tools/go/bin:$HOME/tools/bin:$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
export CODEQL_RAM_MB=12000
export CODEQL_THREADS=2
export CODEQL_TMPDIR="/tmp/$USER/codeql-$SLURM_JOB_ID"
export MINER_CODEQL_TMPDIR="$CODEQL_TMPDIR"

mkdir -p "$CODEQL_TMPDIR"

echo "NODE=$(which node)"
node --version
echo "CODEQL=$(which codeql)"
codeql version

python3 - <<'PY'
from src.scanners.codeql_scanner import scan_snapshot_with_codeql

findings, meta = scan_snapshot_with_codeql(
    "https://github.com/breaking-brake/cc-wf-studio.git",
    "bb7ddadd4e17c9ace31ed2e3a59eb8e3070150ee",
    language="javascript-typescript",
    build_mode="none",
    query_suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
    timeout_seconds=1800,
)

print("STATUS", meta.get("status"))
print("TOTAL", len(findings))

for rule in ("js/file-system-race", "js/missing-origin-check"):
    hits = [f for f in findings if f.get("rule_id") == rule]
    print(rule, len(hits))
    for h in hits:
        print(h.get("file_path"), h.get("line"), h.get("description"))
PY
