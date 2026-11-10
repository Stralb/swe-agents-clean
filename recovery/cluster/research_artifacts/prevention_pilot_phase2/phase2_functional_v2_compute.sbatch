#!/usr/bin/env bash
#SBATCH --job-name=p2_func_v2_compute
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --array=0-1%2
#SBATCH --output=phase2_func_v2_compute_%A_%a.out
#SBATCH --error=phase2_func_v2_compute_%A_%a.err

# Entire Node bootstrap, dependency install, compilation and testing run
# on the allocated bigbatch compute node, never on the login node.
set -euo pipefail

ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
MINER="$HOME/new/malicious-issue-miner-rate-smart"

# Reuse the established research environment.
set -a
source "$MINER/.env.cluster"
set +a
source "$MINER/.venv/bin/activate"

export PHASE2_ROOT="$ROOT"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"

SCRATCH_ROOT="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
mkdir -p "$SCRATCH_ROOT"
JOB_STAGE="$(mktemp -d "$SCRATCH_ROOT/phase2_v2_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}_XXXXXX")"
trap 'rm -rf "$JOB_STAGE"' EXIT

# Unpack the existing evaluator on the compute node, not the login node.
BUNDLE="$ROOT/phase2_functional_v2_bundle.tar.gz"
[[ -f "$BUNDLE" ]] || { echo "Missing $BUNDLE" >&2; exit 3; }
tar -xzf "$BUNDLE" -C "$JOB_STAGE"
EVALUATOR="$JOB_STAGE/phase2_functional_v2.py"
[[ -f "$EVALUATOR" ]] || { echo "Evaluator missing from archive" >&2; exit 3; }

case "${SLURM_ARRAY_TASK_ID:?Submit as an array job}" in
  0) CASE=3504 ;;
  1) CASE=10819 ;;
  *) echo "Unexpected array task: $SLURM_ARRAY_TASK_ID" >&2; exit 2 ;;
esac

# T3 requires Node >=22.13 for the repository-pinned pnpm 11.10.0.
# Bootstrap the runtime inside this job's scratch directory, no shared install.
if [[ "$CASE" == 3504 ]]; then
  NODE_VERSION=22.16.0
  NODE_ARCHIVE="node-v${NODE_VERSION}-linux-x64.tar.xz"
  NODE_STAGE="$JOB_STAGE/node22"
  mkdir -p "$NODE_STAGE"

  BASE_URL="https://nodejs.org/dist/v${NODE_VERSION}"
  echo "Compute-node Node ${NODE_VERSION} bootstrap in $NODE_STAGE"
  curl -fLsS --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 240 \
    "$BASE_URL/$NODE_ARCHIVE" -o "$NODE_STAGE/$NODE_ARCHIVE"
  curl -fLsS --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 60 \
    "$BASE_URL/SHASUMS256.txt" -o "$NODE_STAGE/SHASUMS256.txt"

  # Verify the official archive SHA256 before extraction.
  grep -F "  $NODE_ARCHIVE" "$NODE_STAGE/SHASUMS256.txt" \
    > "$NODE_STAGE/node-checksum.txt"
  (cd "$NODE_STAGE" && sha256sum -c node-checksum.txt)

  mkdir -p "$NODE_STAGE/runtime"
  tar -xJf "$NODE_STAGE/$NODE_ARCHIVE" -C "$NODE_STAGE/runtime" --strip-components=1
  export PATH="$NODE_STAGE/runtime/bin:$PATH"

  # Reuse the pre-downloaded pnpm 11.10.0 Corepack cache when available.
  # pnpm itself runs under this job-local Node22 binary.
  export COREPACK_HOME="$HOME/.cache/node/corepack"

  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 13)) process.exit(1)'
  echo "Node version: $(node --version)"
  echo "Corepack: $(command -v corepack)"
else
  echo "Node version: $(node --version)"
fi

cd "$ROOT"
echo "Case: $CASE; job: $SLURM_JOB_ID; compute host: $(hostname)"
echo "Python: $(command -v python)"
echo "Source: $EVALUATOR"

# Python evaluator uses isolated per-patch npm caches and writes only V2 logs.
python -u "$EVALUATOR" --case "$CASE"
