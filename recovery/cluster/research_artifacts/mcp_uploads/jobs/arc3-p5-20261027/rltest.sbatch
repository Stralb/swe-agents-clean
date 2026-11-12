#!/bin/bash
#SBATCH --job-name=arc3-rltest
#SBATCH --partition=biggpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/rltest-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/rltest-%j.err
set -uo pipefail
mkdir -p out/gpu
{
  echo '== EXISTING VENV PROBE =='
  for v in /home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python /home-mscluster/astrauss/arc26/.venv/bin/python /home-mscluster/astrauss/.conda/envs/apex_env/bin/python /home-mscluster/astrauss/.venvs/rl_lab3/bin/python; do
    if [ -x "$v" ]; then
      echo "CANDIDATE: $v"
      "$v" -c 'import sys; print("EXE",sys.executable); import torch;print("TORCH",torch.__version__,"CUDA",torch.cuda.is_available(),"GPU",(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"))' 2>&1 || :
    fi
  done
  echo '== EXISTING SOURCE PROJECTS =='
  ls -la /home-mscluster/astrauss/arc_rl_final_e012/src/arc_e012 | head -25
  ls -la /home-mscluster/astrauss/RL-ARC-AGI-3-Project/src | head -35
  echo '== TEST ORIGINAL E012 SOURCE =='
  PYTHON=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
  if [ ! -x "$PYTHON" ]; then PYTHON=/home-mscluster/astrauss/arc26/.venv/bin/python; fi
  if [ -x "$PYTHON" ]; then
    cd /home-mscluster/astrauss/arc_rl_final_e012
    export PYTHONPATH="$PWD/src"
    "$PYTHON" -m pytest -q tests/test_core.py 2>&1
    echo "E012_TEST_EXIT=${PIPESTATUS[0]}"
  else
    echo "NO_EXISTING_PYTHON_VENV"
  fi
} > /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/out/gpu/rl_existing_venv_test.log 2>&1
tail -100 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/out/gpu/rl_existing_venv_test.log
