#!/bin/bash
#SBATCH --job-name=e123smoke2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
"$PY" -m py_compile "$ROOT/run_e123_v2.py"
for arm in baseline peer_salience peer_random peer_trained peer_gated peer_trained_salience; do
 "$PY" "$ROOT/run_e123_v2.py" --arm "$arm" --games tu93 vc33 --seed 76 --out "$ROOT/smoke_v2"
done
echo E123_SMOKE_V2_OK
