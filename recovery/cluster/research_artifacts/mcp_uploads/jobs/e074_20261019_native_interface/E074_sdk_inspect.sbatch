#!/bin/bash
#SBATCH --job-name=E074_sdk_inspect
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
for f in "$ROOT/scripts/e038/run_eval.py" "$ROOT/src/e038/evaluate.py" "$ROOT/tests/test_random_agent.py" "$ROOT/vendor/ARC-AGI-3-Agents/agents/templates/random_agent.py";do
 if [ -f "$f" ];then
  echo "===== BEGIN: $f ====="
  sed -n '1,180p' "$f"
  echo "===== END: $f ====="
 fi
done
echo "===== SDK LOCAL REFS ====="
grep -R -l -m 1 "GameAction\|GameState\|arc_agi\|ArcAGI" "$ROOT/src/e038" "$ROOT/scripts/e038" "$ROOT/kaggle" --include='*.py' 2>/dev/null | head -n 20 || true
echo E074_READONLY_NATIVE_INTERFACE_DONE