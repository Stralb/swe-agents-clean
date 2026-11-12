#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 4 ]; then
  echo "usage: $0 <config.env> <blinded_manifest.csv> <patch_dir> <output_dir>" >&2
  exit 2
fi
CONFIG=$1
MANIFEST=$2
PATCHDIR=$3
OUT=$4
mkdir -p "$OUT"
tail -n +2 "$MANIFEST" | while IFS=, read -r order run_id task_file repository base_sha; do
  patch="$PATCHDIR/$run_id.patch"
  if [ ! -f "$patch" ]; then
    mkdir -p "$OUT/$run_id"
    echo MISSING_PATCH > "$OUT/$run_id/apply.status"
    continue
  fi
  "$(dirname "$0")/evaluate_one.sh" "$CONFIG" "$run_id" "$patch" "$OUT"
done
