#!/bin/bash
#SBATCH --job-name=arc3n117compactpush
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
test "$(sha256sum "$OUT/compact_kernel/submission.ipynb" | awk '{print $1}')" = "a5bcc25d1f297185278877c0ea3dfc826baa2b294d55a97ae754d428b8823e64"
test "$(sha256sum "$OUT/private_dataset/my_agent.py" | awk '{print $1}')" = "0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa"
echo "NOTEBOOK_AND_FROZEN_AGENT_CHECKSUMS_OK"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$OUT/compact_push_home"
export HOME="$OUT/compact_push_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" kernels push -p "$OUT/compact_kernel"
echo "KERNEL_PUSH_RETURNED"
"$ROOT/.venv/bin/kaggle" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo "KERNEL_STATUS_QUERIED"
