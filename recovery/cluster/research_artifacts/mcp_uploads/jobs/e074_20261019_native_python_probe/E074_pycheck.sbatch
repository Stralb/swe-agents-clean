#!/bin/bash
#SBATCH --job-name=E074_native_pycheck
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
for PY in /home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python /home-mscluster/astrauss/arc_rl_architecture_e004/.venv/bin/python /home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python3;do
 if [ -x "$PY" ];then
  echo "PYTHON=$PY"
  "$PY" -c 'import sys,importlib.util;print(sys.executable,{x:bool(importlib.util.find_spec(x)) for x in ("arc_agi","arcengine","numpy","torch")})' || true
 fi
done