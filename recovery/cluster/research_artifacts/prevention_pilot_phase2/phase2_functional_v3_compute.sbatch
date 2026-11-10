#!/usr/bin/env bash
#SBATCH --job-name=p2_func_v3
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --array=0-1%2
#SBATCH --output=phase2_func_v3_%A_%a.out
#SBATCH --error=phase2_func_v3_%A_%a.err

# Compute-node only: installation, download, extraction, compilation and tests.
set -euo pipefail

ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
MINER="$HOME/new/malicious-issue-miner-rate-smart"
set -a
source "$MINER/.env.cluster"
set +a
source "$MINER/.venv/bin/activate"
export PHASE2_ROOT="$ROOT"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"

SCRATCH_ROOT="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
mkdir -p "$SCRATCH_ROOT"
JOB_STAGE="$(mktemp -d "$SCRATCH_ROOT/phase2_v3_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}_XXXXXX")"
trap 'rm -rf "$JOB_STAGE"' EXIT
# Keep extracted repositories, node_modules, and package caches within this job stage.
export SLURM_TMPDIR="$JOB_STAGE/work"
mkdir -p "$SLURM_TMPDIR"

BUNDLE="$ROOT/phase2_functional_v3_bundle.tar.gz"
[[ -f "$BUNDLE" ]] || { echo "Missing $BUNDLE" >&2; exit 3; }
tar -xzf "$BUNDLE" -C "$JOB_STAGE"
EVALUATOR="$JOB_STAGE/phase2_functional_v3.py"
[[ -f "$EVALUATOR" ]] || { echo "Missing evaluator" >&2; exit 3; }

case "${SLURM_ARRAY_TASK_ID:?Submit as array job}" in
  0) CASE=3504 ;;
  1) CASE=10819 ;;
  *) echo "Unknown case" >&2; exit 3 ;;
esac

if [[ "$CASE" == 3504 ]]; then
  NODE_VERSION=24.13.1
  NODE_ARCHIVE="node-v${NODE_VERSION}-linux-x64.tar.xz"
  NODE_STAGE="$JOB_STAGE/node24"
  mkdir -p "$NODE_STAGE/runtime"
  BASE_URL="https://nodejs.org/dist/v${NODE_VERSION}"
  echo "Bootstrap Node $NODE_VERSION on compute node $(hostname)"
  curl -fLsS --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 240 \
    "$BASE_URL/$NODE_ARCHIVE" -o "$NODE_STAGE/$NODE_ARCHIVE"
  curl -fLsS --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 60 \
    "$BASE_URL/SHASUMS256.txt" -o "$NODE_STAGE/SHASUMS256.txt"
  grep -F "  $NODE_ARCHIVE" "$NODE_STAGE/SHASUMS256.txt" > "$NODE_STAGE/checksums.txt"
  (cd "$NODE_STAGE" && sha256sum -c checksums.txt)
  tar -xJf "$NODE_STAGE/$NODE_ARCHIVE" -C "$NODE_STAGE/runtime" --strip-components=1
  export PATH="$NODE_STAGE/runtime/bin:$HOME/tools/node/bin:$PATH"
  export COREPACK_HOME="$HOME/.cache/node/corepack"
  echo "Node: $(node --version); Corepack: $(command -v corepack)"
else
  echo "Node: $(node --version); Playwright downloads disabled for Node-only Jest tests"
fi

cd "$ROOT"
python -u "$EVALUATOR" --case "$CASE"
