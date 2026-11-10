#!/bin/bash
#SBATCH --job-name=e123sdkformula
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:07:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e122_e123_joint_audit_20261026
python3 -m py_compile "$ROOT/reconstruct_sdk_score.py"
python3 "$ROOT/reconstruct_sdk_score.py"
echo E122_E123_SDK_SCORE_VERIFICATION_COMPLETE
