#!/bin/bash
#SBATCH --job-name=E103_dev_replay_smoke
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e103_20261020_cross_family_v1/E103_cross_game_eval_v1.py
printf '%s  %s\n' f457413cfdb1346dda93785fbd5f29659966a33ad654ee68bdf11bc6c86b2167 "$SRC" | sha256sum -c -
"$PY" -B - <<'PY'
import importlib.util,os
from pathlib import Path
from src.e027.reproducibility import install_reproducibility
import torch
torch.set_num_threads(1)
install_reproducibility()
path=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e103_20261020_cross_family_v1/E103_cross_game_eval_v1.py')
spec=importlib.util.spec_from_file_location('e103_unseen_frozen',path)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
d=Path('/home-mscluster/astrauss/e103_dev_harness_smoke/E103_smoke_'+os.environ['SLURM_JOB_ID'])
full=e.run_one('vc33',28901,'full',d/'full')
baseline=e.run_one('vc33',28901,'frozen_repeat',d/'frozen_repeat')
assert [x['native_levels'] for x in (full,baseline)]==[3,2]
assert full['native_level_up_events'][-1]['charged_action']==122
assert full['frozen_E097_decisions']>0
assert full['first_frame_SHA256']==baseline['first_frame_SHA256']
print('E103_HARNESS_REPRODUCTION_VERIFIED',{'output':str(d),
'full_levels':full['native_levels'],'baseline_levels':baseline['native_levels'],
'full_level3_at':full['native_level_up_events'][-1]['charged_action']},flush=True)
PY