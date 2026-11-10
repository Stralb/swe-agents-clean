#!/bin/bash
#SBATCH --job-name=arc3n117kaggle
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/slurm-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/slurm-%j.err
set -euo pipefail
umask 077

ROOT=/home-mscluster/astrauss/research_artifacts
JOBROOT="$ROOT/mcp_uploads/jobs/n117_kaggle_20261026_prep1"
WORK="$JOBROOT/work"
ZIP="$ROOT/ARC_AGI3_N117_KAGGLE_RELEASE_20261026.zip"
EXPECTED_ZIP_SHA256=740889d21a00d944e426d29c4bd3967322f1e49453989dfd52ac929bf108be1b

echo "HOST: $(hostname)"
echo "JOB ID: ${SLURM_JOB_ID:-unknown}"
echo "STAGE: verify uploaded release ZIP"
actual="$(sha256sum "$ZIP" | awk '{print $1}')"
if [ "$actual" != "$EXPECTED_ZIP_SHA256" ]; then
  echo "FATAL: uploaded release ZIP SHA256 mismatch"
  exit 2
fi
if [ -e "$WORK" ]; then
  echo "FATAL: work directory already exists; refusing overwrite"
  exit 3
fi
mkdir -p "$WORK/kit"
python3 -m zipfile -e "$ZIP" "$WORK/kit"

echo "STAGE: run local release safety tests"
python3 -m unittest discover -s "$WORK/kit/tests" -v

echo "STAGE: clone published research source"
export GIT_TERMINAL_PROMPT=0
timeout 240 git clone --depth 1 https://github.com/Stralb/arc-agi-3-rl-research.git "$WORK/arc-agi-3-rl-research"

echo "STAGE: verify frozen N117 source and prepare Kaggle notebook"
python3 "$WORK/kit/prepare_release.py" \
    --repo "$WORK/arc-agi-3-rl-research" \
    --output "$WORK/kaggle_kernel" \
    --username arnostrauss \
    --slug arc-agi-3-n117-local-effect-20261026
sha256sum "$WORK/kaggle_kernel/submission.ipynb" "$WORK/arc-agi-3-rl-research/src/best_public_agent.py"
echo "NOTEBOOK_PREPARED"

echo "STAGE: install Kaggle CLI in isolated compute-node virtual environment"
if python3 -m venv "$WORK/.venv"; then
    export PIP_CACHE_DIR="$WORK/pip-cache"
    if "$WORK/.venv/bin/python" -m pip install --disable-pip-version-check kaggle; then
        "$WORK/.venv/bin/kaggle" --version
        echo "KAGGLE_CLI_READY"
    else
        echo "KAGGLE_CLI_INSTALL_FAILED"
        exit 4
    fi
else
    echo "KAGGLE_CLI_VENV_FAILED"
    exit 5
fi

echo "STAGE: authenticate without displaying or modifying credentials"
if [ -s "$HOME/.kaggle/kaggle.json" ] || [ -n "${KAGGLE_API_TOKEN:-}" ] || { [ -n "${KAGGLE_USERNAME:-}" ] && [ -n "${KAGGLE_KEY:-}" ]; }; then
    echo "KAGGLE_CREDENTIALS_PRESENT; attempting notebook push"
    "$WORK/.venv/bin/kaggle" kernels push -p "$WORK/kaggle_kernel"
    echo "KAGGLE_NOTEBOOK_PUSH_REQUESTED"
    "$WORK/.venv/bin/kaggle" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026 || true
else
    echo "KAGGLE_CREDENTIALS_ABSENT; notebook prepared but NOT pushed"
fi
echo "STAGE_COMPLETE. No competition submission was executed."
