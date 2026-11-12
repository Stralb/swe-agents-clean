#!/bin/bash
#SBATCH --job-name=E095_ablation_3seeds
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e095_20261020_multistep_replanning
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' ed5c36f581ee834f35f4a1ef34e8f71311487d68a8800ab529fbbee5e41b0cb0 "$D/E095_online_core_v1.py" | sha256sum -c -
printf '%s  %s\n' 126a274cabd68b34039a5acc712245c5039f5ff46c62559be07744d1764bd727 "$D/E095_native_runner_v1.py" | sha256sum -c -
for SEED in 28901 28902 28903;do
 OUT="/home-mscluster/astrauss/e095_from_reset_research/E095_ablate_seed${SEED}_${SLURM_JOB_ID}"
 echo "E095_SEED_BEGIN $SEED"
 "$PY" -B "$D/E095_native_runner_v1.py" --seed "$SEED" --budget 160 --env-seed 0 --mode full no_memory no_causal no_goal frozen_repeat --out "$OUT"
 echo "E095_SEED_END $SEED $OUT/E095_REPORT.json"
done
echo E095_ABLATIONS_FINISHED