#!/bin/bash
#SBATCH --job-name=E075_vc33_activation
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:25:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py
printf '%s  %s\n' ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7 "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
BASE=/home-mscluster/astrauss/e075_one_game_runs
mkdir -p "$BASE"
OUT="$BASE/E075_VC33_${SLURM_JOB_ID}"
"$PY" -B "$SRC" --seed 28901 --env-seed 0 --budget 160 --out "$OUT"
"$PY" - "$OUT" <<'PY'
import json,sys,pathlib
f=pathlib.Path(sys.argv[1])/'E075_REPORT.json'
v=json.loads(f.read_text())
assert len(v['rows'])==5 and v['development_game_only']=='vc33'
print('E075_SUMMARY',json.dumps({
 'report':str(f),'same_start':v['same_initial_frame'],
 'levels':{r['mode']:r['levels_completed'] for r in v['rows']},
 'activations':{r['mode']:r['counts'] for r in v['rows']}},sort_keys=True))
PY
echo E075_VC33_ACTIVATION_JOB_DONE