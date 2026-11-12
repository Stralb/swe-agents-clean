#!/bin/bash
#SBATCH --job-name=E074_native_wrappers
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "NATIVE_WRAPPER_IMPORTS"
grep -R -n -m 2 -E "arcengine.*(Game|GameAction|GameState)|from arcengine import|arc_agi_3" "$ROOT/scripts" "$ROOT/src" "$ROOT/kaggle" --include='*.py' 2>/dev/null | head -n 60 || true
echo "FIRST_NATIVE_ENTRYPOINTS"
for f in "$ROOT/kaggle/my_agent.py" "$ROOT/kaggle/learner_agent.py" "$ROOT/vendor/ARC-AGI-3-Agents/agents/agent.py"; do
 if [ -f "$f" ];then
  echo "===== $f ====="
  sed -n '1,150p' "$f"
 fi
done
echo DONE