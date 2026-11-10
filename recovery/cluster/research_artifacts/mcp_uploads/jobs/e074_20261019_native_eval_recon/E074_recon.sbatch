#!/bin/bash
#SBATCH --job-name=E074_eval_recon
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "PROJECT_ROOT"
stat -c "%n %s %y" "$ROOT"
echo "ROOT_ENTRIES"
ls -l "$ROOT" | head -n 80
echo "NATIVE_EVALUATION_FILES"
find "$ROOT" -maxdepth 5 -type f \( -name "*eval*.py" -o -name "*rollout*.py" -o -name "*agent*.py" -o -name "*environment*.py" -o -name "*sdk*.py" -o -name "*gym*.py" \) -print 2>/dev/null | head -n 90
echo "SDK_IMPORT_AND_RUN_SAMPLE"
rg -l -m 1 "import arc_agi|from arc_agi|arc_agi_3|GameAction|GameState|GameEnvironment" "$ROOT" -g '*.py' 2>/dev/null | head -n 35 || true
echo "READ_ONLY_RECON_COMPLETE"