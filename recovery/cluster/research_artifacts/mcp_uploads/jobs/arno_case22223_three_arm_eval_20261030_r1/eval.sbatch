#!/bin/bash
#SBATCH --job-name=arno22223_ABC
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=03:00:00
#SBATCH --array=0-2
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/job_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/job_%A_%a.err
set -euo pipefail
umask 077
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -m py_compile "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/eval.py"
ARMS=(A B C)
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/eval.py" "${ARMS[$SLURM_ARRAY_TASK_ID]}"
