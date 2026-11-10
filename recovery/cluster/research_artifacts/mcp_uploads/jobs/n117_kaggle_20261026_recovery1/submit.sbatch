#!/bin/bash
#SBATCH --job-name=arc3n117recoverysubmit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_recovery1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
CLI="$ROOT/.venv/bin/kaggle"
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
test -s "$BASE/preview_output/submission.parquet"
test "$(sha256sum "$BASE/kernel/submission.ipynb" | awk '{print $1}')" = "68305ce3971b5e9771de5d59b5d906a7d11e78e3213b3a6b8d191380a92ed6d7"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/kaggle_home_submit"
export HOME="$BASE/kaggle_home_submit"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "NOTEBOOK_STATUS"
STATUS="$("$CLI" kernels status arnostrauss/arc-agi-3-n117-recovery-20261026)"
echo "$STATUS"
echo "$STATUS" | grep -q "COMPLETE" || { echo "ABORT_NOTEBOOK_NOT_COMPLETE"; exit 10; }
echo "PREEXISTING_SUBMISSIONS"
PREV="$("$CLI" competitions submissions -c arc-prize-2026-arc-agi-3)"
echo "$PREV"
if printf '%s' "$PREV" | grep -q 'N117 recovery fresh kernel'; then
  echo "ABORT_ALREADY_SUBMITTED_RECOVERY"
  exit 11
fi
echo "SUBMITTING_RECOVERY_NOTEBOOK_VERSION_1"
"$CLI" competitions submit -c arc-prize-2026-arc-agi-3 -f submission.parquet -k arnostrauss/arc-agi-3-n117-recovery-20261026 -v 1 -m "N117 recovery fresh kernel: bounded game threads, no recorder, checkpoint unchanged"
echo "OFFICIAL_RECOVERY_SUBMIT_REQUEST_SUCCEEDED"
