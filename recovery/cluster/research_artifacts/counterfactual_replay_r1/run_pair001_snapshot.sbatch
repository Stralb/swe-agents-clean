#!/bin/bash
#SBATCH --job-name=cf_p001_snap
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

OUT="$HOME/research_artifacts/counterfactual_replay_r1"
PAIR="$OUT/S5PAIR001"

URL="https://github.com/gsd-build/gsd-2.git"
BASE="fe0e218954d5e42d2045192f8b8234c0cd56b8c6"

WORK="$PAIR/repo"
ARCHIVE="$PAIR/gsd-2_${BASE:0:8}_base.tar.gz"
FILES="$PAIR/BASE_FILE_MANIFEST.txt"
META="$PAIR/BASE_METADATA.txt"
QC="$PAIR/SNAPSHOT_QC.txt"

mkdir -p "$PAIR"

echo "============================================================"
echo "S5PAIR-001 PRE-CHANGE SNAPSHOT"
echo "============================================================"
echo "HOST=$(hostname)"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "URL=$URL"
echo "BASE=$BASE"
echo

echo "============================================================"
echo "PREFLIGHT"
echo "============================================================"

command -v git >/dev/null 2>&1 || {
    echo "PRECHECK_FAIL: git unavailable"
    exit 2
}

echo "GIT=$(git --version)"

echo
echo "Checking repository connectivity..."

timeout 30 git ls-remote "$URL" HEAD >/dev/null

echo "REMOTE_ACCESS=PASS"

echo
echo "============================================================"
echo "FETCHING EXACT BASE COMMIT"
echo "============================================================"

rm -rf "$WORK"
mkdir -p "$WORK"

git -C "$WORK" init -q
git -C "$WORK" remote add origin "$URL"

timeout 180 git -C "$WORK" fetch \
    --depth=1 \
    origin \
    "$BASE"

FETCHED="$(git -C "$WORK" rev-parse FETCH_HEAD)"

echo "FETCHED=$FETCHED"

if [ "$FETCHED" != "$BASE" ]; then
    echo "PRECHECK_FAIL: fetched commit does not match requested base"
    exit 3
fi

git -C "$WORK" checkout \
    --detach \
    "$BASE" \
    >/dev/null

CHECKED="$(git -C "$WORK" rev-parse HEAD)"

if [ "$CHECKED" != "$BASE" ]; then
    echo "PRECHECK_FAIL: checkout SHA mismatch"
    exit 4
fi

echo "BASE_COMMIT=PASS"

DIRTY="$(git -C "$WORK" status --porcelain)"

if [ -n "$DIRTY" ]; then
    echo "PRECHECK_FAIL: checkout is dirty"
    echo "$DIRTY"
    exit 5
fi

echo "CLEAN_CHECKOUT=PASS"

echo
echo "============================================================"
echo "CREATING SOURCE SNAPSHOT"
echo "============================================================"

rm -f "$ARCHIVE" "$FILES" "$META" "$QC"

git -C "$WORK" archive \
    --format=tar.gz \
    --prefix="gsd-2-${BASE:0:8}/" \
    "$BASE" \
    > "$ARCHIVE"

git -C "$WORK" ls-tree \
    -r \
    --name-only \
    "$BASE" \
    > "$FILES"

{
    echo "S5PAIR-001 BASE SNAPSHOT"
    echo "========================"
    echo
    echo "Repository: $URL"
    echo "Base SHA: $BASE"
    echo "Host: $(hostname)"
    echo
    echo "Commit:"
    git -C "$WORK" show \
        -s \
        --format='commit=%H%nauthor=%an <%ae>%ndate=%aI%nsubject=%s' \
        "$BASE"
    echo
    echo "File count:"
    wc -l < "$FILES"
} > "$META"

ARCHIVE_SIZE="$(stat -c '%s' "$ARCHIVE")"
FILE_COUNT="$(wc -l < "$FILES")"
ARCHIVE_SHA="$(sha256sum "$ARCHIVE" | awk '{print $1}')"

{
    echo "COUNTERFACTUAL REPLAY S5PAIR-001 SNAPSHOT QC"
    echo "============================================"
    echo
    echo "Remote access: PASS"
    echo "Exact base fetch: PASS"
    echo "Clean detached checkout: PASS"
    echo
    echo "Repository: $URL"
    echo "Base SHA: $BASE"
    echo "Files in base tree: $FILE_COUNT"
    echo "Archive bytes: $ARCHIVE_SIZE"
    echo "Archive SHA256: $ARCHIVE_SHA"
    echo
    echo "Archive: $ARCHIVE"
    echo "Manifest: $FILES"
    echo
    echo "SNAPSHOT STATUS: PASS"
} > "$QC"

cat "$QC"

echo
echo "============================================================"
echo "ARCHIVE SIZE"
echo "============================================================"

ls -lh "$ARCHIVE" "$FILES" "$META" "$QC"

echo
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
