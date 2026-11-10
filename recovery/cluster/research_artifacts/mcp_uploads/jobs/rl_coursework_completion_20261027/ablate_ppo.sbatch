#!/bin/bash
#SBATCH --job-name=rl-ppo-ablations
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:25:00
#SBATCH --array=0-11%6
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027
export PYTHONPATH=/home-mscluster/astrauss/RL-ARC-AGI-3-Project:/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026/runtime/python_site
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - "$SLURM_ARRAY_TASK_ID" "$ROOT" <<'PY'
import dataclasses,json,sys
from pathlib import Path
from src.ppo import PPO
from src.config import RunConfig
from src.run import run
q=int(sys.argv[1]);root=Path(sys.argv[2]);out=root/'records';out.mkdir(exist_ok=True)
src=(root/'run_study.sbatch').read_text()
py=src.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
head=py.split('task=int(sys.argv[1])')[0]
ns={};exec(compile(head,'run_study_source','exec'),ns)
PPOVariant=ns['PPOVariant']
class MaskOnly(PPOVariant):
    def observe(self,t):
        return PPO.observe(self,t)  # native reward only, click abstraction still active
for arm in ('I2_frozen','I2_maskonly'):
 game=('ar25','g50t','s5i5','vc33')[q%4];seed=(301,302,303)[q//4]
 dest=out/f'ppo_{arm}_{game}_{seed}.json'
 if dest.exists():continue
 c=RunConfig(algo='ppo',version=arm,game=game,seed=seed,env_seed=47,budget=256,
             threads=1,params={'rollout':64},tag='matched_public_ablation_20261027')
 lr=MaskOnly(c.resolved().arch,c.resolved().params,'I2') if arm=='I2_maskonly' else PPOVariant(c.resolved().arch,c.resolved().params,'I2')
 if arm=='I2_frozen':lr.updates_disabled=True
 result=run(c,learner=lr)
 result.pop('_learner',None);result.pop('scorecard',None)
 result['study']={'algorithm':'ppo','arm':arm,'game':game,'policy_seed':seed,'native_seed':47,
                  'public_exposure':'previously studied public','max_scorer_actions':256}
 dest.write_text(json.dumps(result,indent=2,default=float))
 print(dest.name,'error',result['error'],'score',(result['official_score'] or {}).get('score'),
       'levels',(result['official_score'] or {}).get('levels_completed'),
       'updates',result['learner']['gradient_steps'],flush=True)
PY
