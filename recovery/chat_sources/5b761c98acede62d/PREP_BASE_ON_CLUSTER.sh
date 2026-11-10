#!/usr/bin/env bash
set -euo pipefail
OUT=${1:-$HOME/E_PILOT653_BASE}
REPO_URL=https://github.com/pingcap/ossinsight.git
BASE_SHA=32934c7e9169f214bf65e214e45104b9a1d678b8
mkdir -p "$OUT"
if [ ! -d "$OUT/ossinsight/.git" ]; then
  git clone "$REPO_URL" "$OUT/ossinsight"
fi
cd "$OUT/ossinsight"
git fetch --all --tags --prune
git checkout --detach "$BASE_SHA"
git reset --hard "$BASE_SHA"
git clean -fdx
ACTUAL=$(git rev-parse HEAD)
[ "$ACTUAL" = "$BASE_SHA" ]
printf '%s
' "$ACTUAL" > "$OUT/BASE_SHA.txt"
cd "$OUT"
tar -czf "ossinsight_32934c7e9169f214bf65e214e45104b9a1d678b8.tar.gz" ossinsight
sha256sum "ossinsight_32934c7e9169f214bf65e214e45104b9a1d678b8.tar.gz" > "ossinsight_32934c7e9169f214bf65e214e45104b9a1d678b8.tar.gz.sha256"
echo "$OUT/ossinsight_32934c7e9169f214bf65e214e45104b9a1d678b8.tar.gz"
