#!/bin/bash
#SBATCH --job-name=arc3n117kpush
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts
WORK="$ROOT/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
TOKEN="$HOME/.kaggle/access_token"
NOTEBOOK="$WORK/kaggle_kernel/submission.ipynb"
CLI="$WORK/.venv/bin/kaggle"
EXPECTED_NOTEBOOK_SHA256=0f049935a633a14ba82c0427386e5eef852f3a8972aa205b61a3ca0e70c01acd
echo "NODE: $(hostname)"
test -s "$NOTEBOOK" || { echo MISSING_NOTEBOOK; exit 2; }
test -x "$CLI" || { echo MISSING_KAGGLE_CLI; exit 3; }
test "$(sha256sum "$NOTEBOOK" | awk '{print $1}')" = "$EXPECTED_NOTEBOOK_SHA256" || { echo NOTEBOOK_HASH_MISMATCH; exit 4; }
echo NOTEBOOK_VERIFIED
if [ ! -s "$TOKEN" ]; then echo KAGGLE_TOKEN_NOT_CONFIGURED; exit 5; fi
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
test -n "$KAGGLE_API_TOKEN" || { echo EMPTY_TOKEN; exit 6; }
RUNHOME="$WORK/kaggle_isolated_runhome"
test ! -e "$RUNHOME" || { echo ISOLATED_HOME_ALREADY_EXISTS; exit 7; }
mkdir -m 700 "$RUNHOME"
export HOME="$RUNHOME"
export XDG_CONFIG_HOME="$RUNHOME/.config"
export KAGGLE_CONFIG_DIR="$RUNHOME/.config/kaggle"
"$CLI" --version
"$CLI" kernels push -p "$WORK/kaggle_kernel"
echo NOTEBOOK_PUSH_REQUESTED
"$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo "No official competition submission made"
