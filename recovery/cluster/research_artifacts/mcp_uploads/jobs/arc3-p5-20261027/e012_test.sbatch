#!/bin/bash
#SBATCH --job-name=arc3-dqn-test
#SBATCH --partition=biggpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:04:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/dqntest-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/dqntest-%j.err
set -euo pipefail
mkdir -p out/gpu
cd /home-mscluster/astrauss/arc_rl_final_e012
export PYTHONPATH="$PWD/src"
PYTHON=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PYTHON" -c 'import torch, numpy; print("VENV",torch.__version__,"CUDA",torch.cuda.is_available(),"NUMPY",numpy.__version__)'
set +e
timeout 155s "$PYTHON" -m pytest -q tests/test_core.py > /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/out/gpu/e012_original_tests.txt 2>&1
RC=$?
set -e
echo "E012_ORIGINAL_TESTS_EXIT=$RC"
tail -60 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/out/gpu/e012_original_tests.txt
exit "$RC"
