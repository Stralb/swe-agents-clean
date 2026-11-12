#!/bin/bash
#SBATCH --job-name=E106_frozen_cross_game
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:45:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' 78f3d86b77fd05c4409d0a3d900b7353d534ec095b285677e50abff8c1840d2f "$D/E106_perception_v0.py" | sha256sum -c -
printf '%s  %s\n' 9bbcb04e7f1c2c1797e878e60aceeb4150bdbd0bf5a2346bb661859682dca304 "$D/E106_online_explorer_v0.py" | sha256sum -c -
printf '%s  %s\n' 8e65086961595d2c7700d207c499bf854493399a4f87dc3165c3bb0e9b6791ea "$D/E106_multigame_runner_v0.py" | sha256sum -c -
OUT="/home-mscluster/astrauss/e106_crossfamily_validation/E106_frozen_cross_game_$SLURM_JOB_ID"
"$PY" -B "$D/E106_multigame_runner_v0.py" \
  --games bp35 ka59 ls20 \
  --modes full no_causal event_repeat type_random \
  --seeds 28901 28902 28903 \
  --budget 160 --env-seed 0 --out "$OUT"
echo "E106_FROZEN_CROSS_GAME_FINISHED $OUT/E106_EVALUATION_RESULT.json"