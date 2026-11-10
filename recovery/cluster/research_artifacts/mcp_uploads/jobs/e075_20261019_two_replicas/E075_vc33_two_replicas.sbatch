#!/bin/bash
#SBATCH --job-name=E075_vc33_two_replicas
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py
printf '%s  %s\n' ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7 "$SRC" | sha256sum -c -
for SEED in 28902 28903; do
 OUT="/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_${SLURM_JOB_ID}_seed${SEED}"
 echo "E075_FRESH_SEED_START $SEED $OUT"
 "$PY" -B "$SRC" --seed "$SEED" --env-seed 0 --budget 160 --out "$OUT"
done
"$PY" - <<'PY'
from pathlib import Path
import json,os
root=Path('/home-mscluster/astrauss/e075_one_game_runs')
j=os.environ['SLURM_JOB_ID']
for seed in (28902,28903):
 p=root/f'E075_VC33_{j}_seed{seed}'/'E075_REPORT.json'
 d=json.loads(p.read_text())
 print('E075_REPLICATION',json.dumps({'seed':seed,'same_initial_frame':d['same_initial_frame'],
 'levels':{r['mode']:r['levels_completed'] for r in d['rows']},
 'first_progress':{r['mode']:r['first_progress_at'] for r in d['rows']},
 'native_sdk_scores':{r['mode']:round(r['sdk_score'],6) for r in d['rows']}},sort_keys=True),flush=True)
PY
echo E075_FRESH_REPLICATION_FINISHED