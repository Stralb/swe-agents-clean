#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: ./submit_version.sh <CONFIRMED_KAGGLE_NOTEBOOK_VERSION>" >&2
  exit 2
fi
KERNEL="arnostrauss/arc-agi-3-n117-local-effect-20261026"
VERSION="$1"
echo "Submitting Kaggle competition rerun for $KERNEL, version $VERSION"
echo "This is a REAL leaderboard submission, not a local file upload."
kaggle competitions submit arc-prize-2026-arc-agi-3 \
  -f submission.parquet \
  -k "$KERNEL" \
  -v "$VERSION" \
  -m "N117 local-effect frozen-checkpoint agent; legal native action policy"
