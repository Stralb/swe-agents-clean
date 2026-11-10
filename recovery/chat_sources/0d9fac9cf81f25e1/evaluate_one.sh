#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 <config.env> <run_id> <patch_file> <output_dir>" >&2
  exit 2
fi

CONFIG=$1
RUN_ID=$2
PATCH=$3
OUT=$4
source "$CONFIG"

mkdir -p "$OUT/$RUN_ID"
RUNDIR="$OUT/$RUN_ID"
WORKROOT=$(mktemp -d)
cleanup() { rm -rf "$WORKROOT"; }
trap cleanup EXIT

git clone -q --no-hardlinks "$BASE_REPO" "$WORKROOT/repo"
cd "$WORKROOT/repo"
git checkout -q "$BASE_SHA"
git reset -q --hard "$BASE_SHA"
git clean -q -fdx

printf '%s
' "$RUN_ID" > "$RUNDIR/run_id.txt"
git rev-parse HEAD > "$RUNDIR/base_head.txt"
sha256sum "$PATCH" > "$RUNDIR/patch.sha256"

set +e
git apply --index "$PATCH" >"$RUNDIR/apply.stdout" 2>"$RUNDIR/apply.stderr"
APPLY_RC=$?
set -e
printf '%s
' "$APPLY_RC" > "$RUNDIR/apply.rc"
if [ "$APPLY_RC" -ne 0 ]; then
  exit 0
fi

git diff --cached --binary > "$RUNDIR/applied.patch"

action() {
  local name=$1
  local cmd=$2
  if [ -z "$cmd" ]; then
    printf '%s
' SKIPPED > "$RUNDIR/$name.status"
    return 0
  fi
  set +e
  bash -lc "$cmd" >"$RUNDIR/$name.stdout" 2>"$RUNDIR/$name.stderr"
  local rc=$?
  set -e
  printf '%s
' "$rc" > "$RUNDIR/$name.rc"
  if [ "$rc" -eq 0 ]; then printf '%s
' PASS > "$RUNDIR/$name.status"; else printf '%s
' FAIL > "$RUNDIR/$name.status"; fi
}

action install "$INSTALL_CMD"
action build "$BUILD_CMD"
action functional "$FUNCTIONAL_CMD"
action target_scanner "$TARGET_SCANNER_CMD"
action security_oracle "$SECURITY_ORACLE_CMD"

git status --short > "$RUNDIR/final_status.txt"
