#!/bin/bash
#SBATCH --job-name=e123scorecheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:06:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
import run_e123_l1_v2 as L
R=L.E.R
ORIG_ARC=R.Arcade
last=[None]
def hook(*a,**kw):
 last[0]=ORIG_ARC(*a,**kw);return last[0]
R.Arcade=hook
for arm in ('baseline','l1_d14_salience'):
 for game in ('dc22','lf52','tn36'):
  result=L.E.run_one(game,arm,76)
  card=last[0].get_scorecard()
  if card is None:raise RuntimeError('scorecard not returned')
  env=card.find_environment(game)
  if env is None:raise RuntimeError('Missing game in scorecard')
  score=env.runs[0]
  print('ACTUAL_LOCAL_SDK',game,arm,'LEVELS',result['summary']['levels_completed'],
      'POLICY_COUNT',result['summary']['charged_sdk_actions'],'SDK_ACTIONS',score.actions,
      'SDK_SCORE',round(score.score,9),'SDK_LEVEL_ACTIONS',score.level_actions[:4],
      'SDK_HUMAN_BASELINES',score.level_baseline_actions[:4],flush=True)
print('SCORE_SMOKE_OK')
PY
