#!/bin/bash
#SBATCH --job-name=E107_five_game_pilot
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e107_20261020_multi_family_mechanism
printf '%s  %s\n' 6d6ae06baa96d1ef7fcf0fdac725307af63a5cc1430003ddcde9d3dae8cf94d0 "$D/E107_contrastive_agent_v0.py" | sha256sum -c -
printf '%s  %s\n' f0070a5336a96771a54500477552c2e0461b8be100905b0d1a1188c8999c9252 "$D/E107_multifamily_runner_v0.py" | sha256sum -c -
OUT="/home-mscluster/astrauss/e107_multifamily_dev/E107_five_family_seed28901_$SLURM_JOB_ID"
"$PY" -B "$D/E107_multifamily_runner_v0.py" \
 --games sb26 s5i5 lf52 tn36 g50t \
 --modes contrastive no_contrast no_reliability no_drift no_context e106_frozen event_repeat type_random \
 --seeds 28901 --budget 160 --env-seed 0 --out "$OUT"
echo "E107_DEV_PILOT_COMPLETED $OUT/E107_EVALUATION_RESULT.json"