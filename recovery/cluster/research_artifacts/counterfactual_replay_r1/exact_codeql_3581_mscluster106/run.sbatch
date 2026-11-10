#!/bin/bash
#SBATCH --job-name=cf_exact3581
#SBATCH --partition=biggpu
#SBATCH --nodelist=mscluster106
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/exact_codeql_3581_mscluster106/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/exact_codeql_3581_mscluster106/error.txt

set -euo pipefail

export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
export CODEQL_RAM_MB=24000
export CODEQL_THREADS=2
export CODEQL_TMPDIR="/tmp/$USER/codeql"
export MINER_CODEQL_TMPDIR="/tmp/$USER/codeql"

mkdir -p "$CODEQL_TMPDIR"

echo "=== ENV ==="
hostname
which codeql
codeql version
which node
node --version

SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
REPO_URL="https://github.com/breaking-brake/cc-wf-studio.git"
BASE="68d4f9c0ac43e54266205b80fea328da4dd535a2"
HEAD="bb7ddadd4e17c9ace31ed2e3a59eb8e3070150ee"

WORK="$(mktemp -d -p "$CODEQL_TMPDIR" exact3581-)"
trap 'rm -rf "$WORK"' EXIT

scan_one () {
    LABEL="$1"
    SHA="$2"
    SRC="$WORK/$LABEL-src"
    DB="$WORK/$LABEL-db"
    SARIF="$WORK/$LABEL.sarif"

    git clone -q --depth=1 "$REPO_URL" "$SRC"
    git -C "$SRC" fetch -q --depth=1 origin "$SHA"
    git -C "$SRC" checkout -q "$SHA"

    codeql database create "$DB" \
      --language=javascript-typescript \
      --source-root="$SRC" \
      --ram=24000 \
      --threads=2 \
      --build-mode=none

    codeql database analyze "$DB" "$SUITE" \
      --format=sarif-latest \
      --output="$SARIF" \
      --ram=24000 \
      --threads=2

    python3 - "$LABEL" "$SARIF" <<'PY'
import json, sys

label, path = sys.argv[1:]
d = json.load(open(path))

targets = {
    "js/file-system-race",
    "js/missing-origin-check",
}

counts = {x: 0 for x in targets}
total = 0

for run in d.get("runs", []):
    for result in run.get("results", []):
        total += 1
        rid = result.get("ruleId")
        if rid in counts:
            counts[rid] += 1
            loc = ((result.get("locations") or [{}])[0]
                   .get("physicalLocation") or {})
            artifact = (loc.get("artifactLocation") or {}).get("uri")
            line = (loc.get("region") or {}).get("startLine")
            print("TARGET", label, rid, artifact, line)

print("SUMMARY", label, "total=", total,
      "file-system-race=", counts["js/file-system-race"],
      "missing-origin-check=", counts["js/missing-origin-check"])
PY
}

echo
echo "=== BASE ==="
scan_one base "$BASE"

echo
echo "=== HEAD ==="
scan_one head "$HEAD"
