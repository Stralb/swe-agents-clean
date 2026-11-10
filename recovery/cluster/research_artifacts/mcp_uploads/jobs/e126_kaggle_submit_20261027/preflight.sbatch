#!/bin/bash
#SBATCH --job-name=e126preflight
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo "PYTHON_AVAILABLE $(test -x "$PY" && echo yes || echo no)"
echo "KAGGLE_CLI_AVAILABLE $(test -x "$KG" && echo yes || echo no)"
echo "PEER_MODEL_AVAILABLE $(test -f /home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt && echo yes || echo no)"
for d in "$ROOT"/e128* "$ROOT"/*kaggle* "$ROOT"/*release*; do if test -d "$d"; then echo "DIR $(basename "$d")"; fi; done
"$KG" --version
"$KG" kernels push --help | head -35
"$KG" competitions submit --help | head -60
echo PREFLIGHT_OK
