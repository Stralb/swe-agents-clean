#!/bin/bash
#SBATCH --job-name=e123native25
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
for arm in baseline peer_salience peer_random peer_trained peer_gated peer_trained_salience; do
 echo START_ARM "$arm"
 "$PY" "$ROOT/run_e123_v2.py" --arm "$arm" --seed 76 --out "$ROOT/results" --resume
 echo END_ARM "$arm"
done
echo E123_150_NATIVE_EPISODES_DONE
