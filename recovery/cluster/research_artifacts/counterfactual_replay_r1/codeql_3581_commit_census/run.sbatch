#!/bin/bash
#SBATCH --job-name=ql3581hist
#SBATCH --partition=batch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_commit_census/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_commit_census/error.txt

set -euo pipefail

export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"

BASE="68d4f9c0ac43e54266205b80fea328da4dd535a2"
HEAD="bb7ddadd4e17c9ace31ed2e3a59eb8e3070150ee"
URL="https://github.com/breaking-brake/cc-wf-studio.git"

PACK="$HOME/.codeql/packages/codeql/javascript-queries/2.3.11"
Q1="$PACK/Security/CWE-367/FileSystemRace.ql"
Q2="$(find "$PACK/Security" -name 'MissingOriginCheck.ql' -print -quit)"

echo "CODEQL=$(codeql version --format=terse 2>/dev/null || codeql version | head -1)"
echo "Q1=$Q1"
echo "Q2=$Q2"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

REPO="$WORK/repo"

git init -q "$REPO"
git -C "$REPO" remote add origin "$URL"
git -C "$REPO" fetch -q --depth=100 origin "$BASE" "$HEAD"

COMMITS="$WORK/commits.txt"
{
    echo "$BASE"
    git -C "$REPO" rev-list --reverse "$BASE..$HEAD"
} > "$COMMITS"

echo
echo "=== COMMITS ==="
nl -ba "$COMMITS"

echo
echo "=== SOURCE STATES ==="

while read -r SHA; do
    git -C "$REPO" checkout -q -f "$SHA"

    COUNT="$(git -C "$REPO" ls-files '*.js' '*.jsx' '*.ts' '*.tsx' | wc -l)"
    DATE="$(git -C "$REPO" show -s --format='%cI' "$SHA")"

    F1="$REPO/src/extension/services/commentary-jsonl-watcher.ts"
    F2="$REPO/src/webview/src/components/CommentaryPanel.tsx"

    H1="MISSING"
    H2="MISSING"

    [ -f "$F1" ] && H1="$(sha256sum "$F1" | cut -d' ' -f1)"
    [ -f "$F2" ] && H2="$(sha256sum "$F2" | cut -d' ' -f1)"

    echo "$SHA files=$COUNT date=$DATE watcher=$H1 panel=$H2"
done < "$COMMITS"

echo
echo "=== CODEQL TARGET CENSUS ==="

N=0

while read -r SHA; do
    N=$((N+1))

    SRC="$WORK/src-$N"
    DB="$WORK/db-$N"
    SARIF="$WORK/out-$N.sarif"

    mkdir -p "$SRC"
    git -C "$REPO" archive "$SHA" | tar -x -C "$SRC"

    echo
    echo "SCAN $N $SHA"

    codeql database create "$DB" \
      --language=javascript-typescript \
      --source-root="$SRC" \
      --build-mode=none \
      --ram=12000 \
      --threads=2 >/dev/null

    codeql database analyze "$DB" "$Q1" "$Q2" \
      --format=sarif-latest \
      --output="$SARIF" \
      --ram=12000 \
      --threads=2 >/dev/null

    python3 - "$SHA" "$SARIF" <<'PY'
import json, sys

sha, fn = sys.argv[1:]
d = json.load(open(fn))

wanted = {
    "js/file-system-race": 0,
    "js/missing-origin-check": 0,
}

for run in d.get("runs", []):
    for r in run.get("results", []):
        rid = r.get("ruleId")

        if rid not in wanted:
            continue

        wanted[rid] += 1

        p = (
            ((r.get("locations") or [{}])[0]
             .get("physicalLocation") or {})
        )

        print(
            "HIT",
            sha,
            rid,
            (p.get("artifactLocation") or {}).get("uri"),
            (p.get("region") or {}).get("startLine"),
        )

print(
    "RESULT",
    sha,
    "race=", wanted["js/file-system-race"],
    "origin=", wanted["js/missing-origin-check"],
)
PY

    rm -rf "$DB" "$SRC"
done < "$COMMITS"

echo
echo "STATUS=DONE"
