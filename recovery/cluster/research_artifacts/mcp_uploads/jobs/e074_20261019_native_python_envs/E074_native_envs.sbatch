#!/bin/bash
#SBATCH --job-name=E074_python_envs
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "NATIVE_RECENT_SCRIPTS_PYTHON_SETUPS"
grep -R -n -m 1 -E "(venv/bin/python|python3|source .*activate|arc_agi==|pip install.*arc)" "$ROOT/slurm" "$ROOT/scripts" --include='*.sbatch' --include='*.slurm' --include='*.sh' 2>/dev/null | head -n 90 || true
echo "USER_VENV_CANDIDATES"
ls -ld /home-mscluster/astrauss/.venv /home-mscluster/astrauss/venv* /home-mscluster/astrauss/*venv* /home-mscluster/astrauss/arc* /home-mscluster/astrauss/RL-ARC-AGI-3-Project/.venv /home-mscluster/astrauss/.local/bin/python* 2>/dev/null | head -n 80 || true
echo "SYSTEM_PYTHON_ARC_MODULE"
for BIN in python python3 /usr/bin/python3 /home-mscluster/astrauss/arc26/.venv/bin/python; do
 if command -v "$BIN" >/dev/null 2>&1;then
  echo "BIN $BIN"
  "$BIN" -c 'import sys,importlib.util;print(sys.executable,{"arc_agi":bool(importlib.util.find_spec("arc_agi")),"arcengine":bool(importlib.util.find_spec("arcengine")),"torch":bool(importlib.util.find_spec("torch"))})' || true
 fi
done
echo E074_PYTHON_ENV_READ_ONLY_DONE