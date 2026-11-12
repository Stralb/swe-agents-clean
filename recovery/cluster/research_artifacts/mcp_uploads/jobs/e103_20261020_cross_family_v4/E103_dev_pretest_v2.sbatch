#!/bin/bash
#SBATCH --job-name=E103_dev_smoke_v2
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e103_20261020_cross_family_v4/E103_cross_game_eval_v2.py
printf '%s  %s\n' e49ed3ff37a50cedd32959ba4e815d7d379eab1d83f378efeabdf4414b88520f "$SRC" | sha256sum -c -
"$PY" -B - <<'PY'
import importlib.util,os,sys
from pathlib import Path
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.e027.reproducibility import install_reproducibility
import torch
torch.set_num_threads(1)
install_reproducibility()
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e103_20261020_cross_family_v4/E103_cross_game_eval_v2.py')
spec=importlib.util.spec_from_file_location('e103_harness_smoke',p)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
d=Path('/home-mscluster/astrauss/e103_dev_harness_smoke/E103_v2_smoke_'+os.environ['SLURM_JOB_ID'])
full=e.run_one('vc33',28901,'full',d/'full')
baseline=e.run_one('vc33',28901,'frozen_repeat',d/'frozen_repeat')
assert full['native_levels']==3 and baseline['native_levels']==2,(full['native_levels'],baseline['native_levels'])
assert full['native_level_up_events'][-1]['charged_action']==122
assert full['frozen_E097_decisions']>0
assert full['first_frame_SHA256']==baseline['first_frame_SHA256']
assert full['actions_charged']==160 and full['explicit_policy_decisions']==159
print('E103_FROZEN_POLICY_HARNESS_REPRODUCED',{'output':str(d),
 'full':full['native_levels'],'repeat':baseline['native_levels'],
 'native_level3_action':122,'charges':full['actions_charged'],
 'explicit_decisions':full['explicit_policy_decisions']},flush=True)
PY