#!/bin/bash
#SBATCH --job-name=E078_rl_code_contract
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
for f in src/dqn.py src/ppo.py src/run.py scripts/compare_dqn_baselines.sh README.md configs/base.yaml src/config.py src/networks.py src/replay.py src/environment.py kaggle/my_agent.py; do
 if [ -f "$P/$f" ];then echo "======== BEGIN $f =======";sed -n '1,250p' "$P/$f";echo "======== END $f =======";fi
done
echo ==== AVAILABLE PYTHON FILES ====
find "$P/src" -maxdepth 2 -name "*.py" -printf '%P\n' | head -n 80
echo ==== DONE ====